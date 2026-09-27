#!/usr/bin/env python3
# encoding: utf-8
"""
行人检测节点（HOG 版，跑在【小主机】上，无需笔记本 / 无需 AVX2 / 无需 torch）：
订阅 usb_cam 原始图像，用 OpenCV 自带 HOG+SVM 行人检测器找「人」，
把最像人的框发到 /person/bbox。与 person_follow.py 配套，可整机单机跑。

优点：零额外依赖（OpenCV 自带），纯 CPU，小主机 J3160 就能跑，图像不用走 WiFi。
缺点：精度远低于 YOLOv8，对侧身/转身/半身/远距离小目标容易漏检或误检。

运行（小主机，先起 usb_cam）：
  python3 person_detect_hog.py _scale:=1.05 _win_stride:=8

参数（均可用 _key:=value 覆盖）：
  ~scale         图像金字塔缩放，默认 1.05（越小越慢、越能找远处小目标）
  ~win_stride    滑动步长，默认 8（越大越快、越粗糙）
  ~publish_debug 是否发调试图到 /person/debug/compressed，默认 true
"""

import cv2
import rospy
from cv_bridge import CvBridge
from sensor_msgs.msg import CompressedImage, Image, RegionOfInterest


class HogPersonDetector(object):
    def __init__(self):
        rospy.init_node('person_detector_hog')
        self.bridge = CvBridge()
        self.scale = rospy.get_param('~scale', 1.05)
        self.win_stride = rospy.get_param('~win_stride', 8)
        self.publish_debug = rospy.get_param('~publish_debug', True)

        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

        self.bbox_pub = rospy.Publisher('/person/bbox', RegionOfInterest, queue_size=1)
        self.debug_pub = None
        if self.publish_debug:
            self.debug_pub = rospy.Publisher('/person/debug/compressed', CompressedImage, queue_size=1)
        self.sub = rospy.Subscriber('/usb_cam/image_raw', Image, self.cb,
                                    queue_size=1, buff_size=2 ** 24)
        rospy.loginfo('HOG 行人检测就绪，等待 /usb_cam/image_raw ...')

    def cb(self, msg):
        try:
            img = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
        except Exception as e:
            rospy.logwarn('转换图像失败: %s', e)
            return
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        rects, weights = self.hog.detectMultiScale(
            gray, winStride=(self.win_stride, self.win_stride),
            padding=(8, 8), scale=self.scale)

        if rects is None or len(rects) == 0:
            return

        # 挑 SVM 分数最高的框（最像人）
        best_i = int(weights.argmax())
        x, y, w, h = rects[best_i]

        roi = RegionOfInterest()
        roi.x_offset = int(x)
        roi.y_offset = int(y)
        roi.width = int(w)
        roi.height = int(h)
        roi.do_rectify = False
        self.bbox_pub.publish(roi)

        if self.publish_debug:
            cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(img, 'person %.2f' % weights[best_i],
                        (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            self.debug_pub.publish(self.bridge.cv2_to_compressed_imgmsg(img))


if __name__ == '__main__':
    try:
        HogPersonDetector()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
