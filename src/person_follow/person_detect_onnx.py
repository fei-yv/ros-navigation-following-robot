#!/usr/bin/env python3
# encoding: utf-8
"""
行人检测节点（ONNX 版，跑在【小主机】上，无需笔记本 / 无需 AVX2 / 无需 torch）：
用 onnxruntime 加载 YOLOv8 导出的 yolov8n.onnx，检测「人」(COCO class 0)，
把置信度最高的人的框发到 /person/bbox。精度等同 YOLOv8，且整机单机跑。

前提：先把 yolov8n.onnx 放到 models/ 目录（在笔记本用 ultralytics 导出，见文末）。

运行（小主机，先起 usb_cam）：
  python3 person_detect_onnx.py _model:=/home/robot/catkin_ws/src/person_follow/models/yolov8n.onnx _conf:=0.5

参数（均可用 _key:=value 覆盖）：
  ~model         onnx 模型路径，默认 /home/robot/catkin_ws/src/person_follow/models/yolov8n.onnx
  ~conf          置信度阈值，默认 0.5
  ~imgsz         模型输入边长，默认 320（须与导出时一致；当前 onnx 是 320 输入）
  ~iou           NMS IoU 阈值，默认 0.45
  ~publish_debug 是否发调试图到 /person/debug/compressed，默认 true
"""

import cv2
import numpy as np
import onnxruntime as ort
import rospy
from cv_bridge import CvBridge
from sensor_msgs.msg import CompressedImage, Image, RegionOfInterest

# COCO 类别索引：0 = person
PERSON_CLASS = 0


def letterbox(img, new_shape=640, color=(114, 114, 114)):
    """保持宽高比缩放并填充到 new_shape x new_shape，返回 (img, r, dw, dh)。"""
    h, w = img.shape[:2]
    r = min(new_shape / float(w), new_shape / float(h))
    nw, nh = int(round(w * r)), int(round(h * r))
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    dw = (new_shape - nw) / 2.0
    dh = (new_shape - nh) / 2.0
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    img = cv2.copyMakeBorder(resized, top, bottom, left, right,
                             cv2.BORDER_CONSTANT, value=color)
    return img, r, dw, dh


def nms(boxes, scores, iou_thr=0.45):
    """简单 NMS，boxes 为 [N,4] xyxy，scores 为 [N]，返回保留的索引列表。"""
    order = scores.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(int(i))
        if order.size == 1:
            break
        xx1 = np.maximum(boxes[i, 0], boxes[order[1:], 0])
        yy1 = np.maximum(boxes[i, 1], boxes[order[1:], 1])
        xx2 = np.minimum(boxes[i, 2], boxes[order[1:], 2])
        yy2 = np.minimum(boxes[i, 3], boxes[order[1:], 3])
        inter = np.maximum(0.0, xx2 - xx1) * np.maximum(0.0, yy2 - yy1)
        area_i = (boxes[i, 2] - boxes[i, 0]) * (boxes[i, 3] - boxes[i, 1])
        area_o = (boxes[order[1:], 2] - boxes[order[1:], 0]) * \
                 (boxes[order[1:], 3] - boxes[order[1:], 1])
        iou = inter / (area_i + area_o - inter + 1e-9)
        order = order[np.where(iou <= iou_thr)[0] + 1]
    return keep


class OnnxPersonDetector(object):
    def __init__(self):
        rospy.init_node('person_detector_onnx')
        self.bridge = CvBridge()
        model = rospy.get_param('~model', '/home/robot/catkin_ws/src/person_follow/models/yolov8n.onnx')
        self.conf_th = rospy.get_param('~conf', 0.5)
        self.imgsz = rospy.get_param('~imgsz', 320)
        self.iou_thr = rospy.get_param('~iou', 0.45)
        self.publish_debug = rospy.get_param('~publish_debug', True)

        self.sess = ort.InferenceSession(model, providers=['CPUExecutionProvider'])
        self.in_name = self.sess.get_inputs()[0].name
        self.out_name = self.sess.get_outputs()[0].name
        rospy.loginfo('onnx 模型加载完成: %s', model)

        self.bbox_pub = rospy.Publisher('/person/bbox', RegionOfInterest, queue_size=1)
        self.debug_pub = None
        if self.publish_debug:
            self.debug_pub = rospy.Publisher('/person/debug/compressed', CompressedImage, queue_size=1)
        self.sub = rospy.Subscriber('/usb_cam/image_raw', Image, self.cb,
                                    queue_size=1, buff_size=2 ** 24)
        rospy.loginfo('person_detector_onnx 就绪，等待 /usb_cam/image_raw ...')

    def cb(self, msg):
        try:
            img = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
        except Exception as e:
            rospy.logwarn('转换图像失败: %s', e)
            return
        orig_h, orig_w = img.shape[:2]

        lb, r, dw, dh = letterbox(img, self.imgsz)
        rgb = lb[:, :, ::-1]  # BGR -> RGB
        blob = np.ascontiguousarray(rgb.transpose(2, 0, 1)[None], dtype=np.float32) / 255.0

        out = self.sess.run([self.out_name], {self.in_name: blob})[0]  # [1,84,8400]
        pred = out[0].transpose(1, 0)  # [8400, 84]

        boxes = pred[:, :4]                       # cx,cy,w,h（letterbox 坐标）
        person_scores = pred[:, 4 + PERSON_CLASS]  # class 0 分数

        idx = np.where(person_scores > self.conf_th)[0]
        if idx.size == 0:
            return

        sc = person_scores[idx]
        bx = boxes[idx]
        cx, cy, w, h = bx[:, 0], bx[:, 1], bx[:, 2], bx[:, 3]
        # 反 letterbox 映射回原图坐标
        x1 = (cx - w / 2.0 - dw) / r
        y1 = (cy - h / 2.0 - dh) / r
        x2 = (cx + w / 2.0 - dw) / r
        y2 = (cy + h / 2.0 - dh) / r
        xyxy = np.stack([x1, y1, x2, y2], axis=1)

        keep = nms(xyxy, sc, self.iou_thr)
        if not keep:
            return

        # NMS 后取分数最高的人
        best = max(keep, key=lambda k: sc[k])
        px1 = max(0, int(xyxy[best, 0]))
        py1 = max(0, int(xyxy[best, 1]))
        px2 = min(orig_w, int(xyxy[best, 2]))
        py2 = min(orig_h, int(xyxy[best, 3]))

        roi = RegionOfInterest()
        roi.x_offset = px1
        roi.y_offset = py1
        roi.width = max(0, px2 - px1)
        roi.height = max(0, py2 - py1)
        roi.do_rectify = False
        self.bbox_pub.publish(roi)

        if self.publish_debug:
            cv2.rectangle(img, (px1, py1), (px2, py2), (0, 255, 0), 2)
            cv2.putText(img, 'person %.2f' % sc[best], (px1, py1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            self.debug_pub.publish(self.bridge.cv2_to_compressed_imgmsg(img))


if __name__ == '__main__':
    try:
        OnnxPersonDetector()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
