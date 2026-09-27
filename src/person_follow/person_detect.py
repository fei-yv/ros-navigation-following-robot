#!/usr/bin/env python3
# encoding: utf-8
"""
人检测节点（跑在【笔记本】上）：订阅小主机 usb_cam 发来的压缩图像，
用 YOLOv8n 检测「人」(COCO class 0)，把置信度最高的人的 bbox 发到
/person/bbox（sensor_msgs/RegionOfInterest，像素坐标，对应原始图像分辨率）。

依赖：ultralytics（笔记本需 pip install ultralytics）
运行（笔记本，先 source ROS 并把 ROS_MASTER_URI 指向小主机）：
  python3 person_detect.py _model:=yolov8n.pt _conf:=0.5 _imgsz:=640

参数（均可用 _key:=value 覆盖）：
  ~model         模型文件，默认 yolov8n.pt（首次运行会自动下载）
  ~conf          置信度阈值，默认 0.5
  ~imgsz         推理输入边长，默认 640
  ~publish_debug 是否发布带框的调试图像到 /person/debug/compressed，默认 true
"""

import cv2
import rospy
from cv_bridge import CvBridge
from sensor_msgs.msg import CompressedImage, RegionOfInterest
from ultralytics import YOLO


class PersonDetector(object):
    def __init__(self):
        rospy.init_node('person_detector')
        self.bridge = CvBridge()

        model = rospy.get_param('~model', 'yolov8n.pt')
        self.conf_th = rospy.get_param('~conf', 0.5)
        self.imgsz = rospy.get_param('~imgsz', 640)
        self.publish_debug = rospy.get_param('~publish_debug', True)

        rospy.loginfo('加载模型 %s ...', model)
        self.model = YOLO(model)
        rospy.loginfo('模型加载完成')

        self.bbox_pub = rospy.Publisher('/person/bbox', RegionOfInterest, queue_size=1)
        self.debug_pub = None
        if self.publish_debug:
            self.debug_pub = rospy.Publisher('/person/debug/compressed', CompressedImage, queue_size=1)

        self.sub = rospy.Subscriber('/usb_cam/image_raw/compressed', CompressedImage,
                                    self.cb, queue_size=1, buff_size=2 ** 24)
        rospy.loginfo('person_detector 就绪，等待 /usb_cam/image_raw/compressed ...')

    def cb(self, msg):
        try:
            img = self.bridge.compressed_imgmsg_to_cv2(msg, 'bgr8')
        except Exception as e:
            rospy.logwarn('解压图像失败: %s', e)
            return

        results = self.model(img, verbose=False, imgsz=self.imgsz,
                             conf=self.conf_th)[0]

        best = None  # (conf, x1, y1, x2, y2)
        for box in results.boxes:
            if int(box.cls[0]) != 0:  # 只要 person
                continue
            conf = float(box.conf[0])
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            if best is None or conf > best[0]:
                best = (conf, x1, y1, x2, y2)

        if best is None:
            return

        conf, x1, y1, x2, y2 = best
        roi = RegionOfInterest()
        roi.x_offset = int(x1)
        roi.y_offset = int(y1)
        roi.width = int(x2 - x1)
        roi.height = int(y2 - y1)
        roi.do_rectify = False
        self.bbox_pub.publish(roi)

        if self.publish_debug:
            cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)),
                          (0, 255, 0), 2)
            cv2.putText(img, 'person %.2f' % conf, (int(x1), int(y1) - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            self.debug_pub.publish(self.bridge.cv2_to_compressed_imgmsg(img))


if __name__ == '__main__':
    try:
        PersonDetector()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
