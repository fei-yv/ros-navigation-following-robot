#!/usr/bin/env python3
# encoding: utf-8
"""
跟随控制节点（跑在【小主机】上）：订阅 /person/bbox，按人在画面中的位置/大小算速度，
直接发 /cmd_vel（与键盘遥控同一控制口，无需 move_base / amcl / 地图）。

三块功能：
  1. 比例跟随：角速度对齐画面中心，线速度维持目标距离（带死区消抖，不左右摆头）
  2. 丢失搜索：丢目标超过 lost_timeout 秒后，原地慢速转圈，直到重新框到人
  3. 避障：订阅 /scan（雷达），前方障碍物 < stop_dist 停车、< slow_dist 减速

运行（小主机，先起底盘 + 雷达 + 摄像头 + 检测）：
  python3 person_follow.py \
      _target_depth:=2.0 _K_depth:=900 _search_angular:=0.3

参数（均可用 _key:=value 覆盖）：
  ~img_width        画面宽度像素，须与 usb_cam 分辨率一致，默认 640
  ~k_angular        角速度增益，默认 0.0015（越小越不摆头，但转向越慢）
  ~k_linear         线速度增益，默认 0.3
  ~target_depth     目标跟随距离(米)，默认 2.0
  ~K_depth          单目估距系数 = 焦距(px)*人高(m)，默认 900，需实测标定
  ~max_angular      角速度限幅(rad/s)，默认 0.25
  ~max_linear       线速度限幅(m/s)，默认 0.3
  ~lost_timeout     丢目标进入搜索的等待时间(秒)，默认 1.0
  ~angular_deadzone 角速度死区(像素)，|偏移|<此值不转，默认 60（消摆头）
  ~linear_deadzone  线速度死区(米)，|距离误差|<此值不进不退，默认 0.2
  ~search_angular   丢失后原地转圈的角速度(rad/s)，默认 0.3
  ~search_direction 搜索转向方向(+1 左 / -1 右)，默认 +1
  ~stop_dist        前方障碍急停距离(米)，默认 0.30
  ~slow_dist        前方障碍开始减速的距离(米)，默认 0.60
  ~front_angle      前方锥形避障半角(度)，默认 30
"""

import math

import rospy
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan, RegionOfInterest


class PersonFollower(object):
    def __init__(self):
        rospy.init_node('person_follower')

        # 跟随参数
        self.img_width = rospy.get_param('~img_width', 640)
        self.k_angular = rospy.get_param('~k_angular', 0.0015)
        self.k_linear = rospy.get_param('~k_linear', 0.3)
        self.target_depth = rospy.get_param('~target_depth', 2.0)
        self.K_depth = rospy.get_param('~K_depth', 900.0)
        self.max_angular = rospy.get_param('~max_angular', 0.25)
        self.max_linear = rospy.get_param('~max_linear', 0.3)
        self.alpha = rospy.get_param('~alpha', 0.3)                    # 低通滤波系数(0~1，越小越平滑、越消摆头)
        self.turn_slowdown = rospy.get_param('~turn_slowdown', 0.8)    # 转向降速强度
        self.lost_timeout = rospy.get_param('~lost_timeout', 1.0)
        self.angular_deadzone = rospy.get_param('~angular_deadzone', 60)
        self.linear_deadzone = rospy.get_param('~linear_deadzone', 0.2)

        # 搜索参数
        self.search_angular = rospy.get_param('~search_angular', 0.3)
        self.search_direction = rospy.get_param('~search_direction', 1)

        # 避障参数
        self.stop_dist = rospy.get_param('~stop_dist', 0.30)
        self.slow_dist = rospy.get_param('~slow_dist', 0.60)
        self.front_angle_rad = math.radians(rospy.get_param('~front_angle', 45))

        # 状态
        self.last_bbox = None
        self.last_seen = rospy.Time(0)
        self.min_front = -1.0  # 前方最近障碍距离，<0 表示雷达无数据
        self.filt_lin = 0.0
        self.filt_ang = 0.0

        self.cmd_pub = rospy.Publisher('/cmd_vel', Twist, queue_size=1)
        self.bbox_sub = rospy.Subscriber('/person/bbox', RegionOfInterest,
                                         self.bbox_cb, queue_size=1)
        self.scan_sub = rospy.Subscriber('/scan', LaserScan, self.scan_cb, queue_size=1)
        self.timer = rospy.Timer(rospy.Duration(0.1), self.control)
        rospy.loginfo('person_follower 就绪（跟随 + 搜索 + 避障），等待 /person/bbox 与 /scan ...')

    def bbox_cb(self, msg):
        self.last_bbox = (msg.x_offset, msg.y_offset, msg.width, msg.height)
        self.last_seen = rospy.Time.now()

    def scan_cb(self, msg):
        n = len(msg.ranges)
        inc = msg.angle_increment
        if n == 0 or inc <= 0:
            self.min_front = -1.0
            return
        center = int(round((0.0 - msg.angle_min) / inc))
        half = int(round(self.front_angle_rad / inc))
        lo = max(0, center - half)
        hi = min(n, center + half + 1)
        mn = None
        for v in msg.ranges[lo:hi]:
            if math.isfinite(v) and v > 0.05:
                if mn is None or v < mn:
                    mn = v
        self.min_front = mn if mn is not None else -1.0

    def control(self, event):
        twist = Twist()
        now = rospy.Time.now()
        lost = (self.last_bbox is None or
                (now - self.last_seen).to_sec() > self.lost_timeout)

        raw_ang = 0.0
        raw_lin = 0.0
        if lost:
            # 搜索模式：原地慢速转圈，直到重新框到人
            raw_ang = self.search_direction * self.search_angular
            raw_lin = 0.0
        else:
            x, y, w, h = self.last_bbox
            cx = x + w / 2.0
            err_x = cx - self.img_width / 2.0

            # 角速度：带死区，避免左右摆头
            if abs(err_x) < self.angular_deadzone:
                raw_ang = 0.0
            else:
                raw_ang = -self.k_angular * err_x

            # 线速度：带死区，避免前后抖
            depth = self.K_depth / float(h) if h > 0 else self.target_depth
            err_d = depth - self.target_depth
            if abs(err_d) < self.linear_deadzone:
                raw_lin = 0.0
            else:
                raw_lin = self.k_linear * err_d

        # 限幅
        raw_ang = max(-self.max_angular, min(self.max_angular, raw_ang))
        raw_lin = max(-self.max_linear, min(self.max_linear, raw_lin))

        # 低通滤波：平滑输出，抑制打滑/抖动引起的突变
        self.filt_ang += (1.0 - self.alpha) * (raw_ang - self.filt_ang)
        self.filt_lin += (1.0 - self.alpha) * (raw_lin - self.filt_lin)
        twist.angular.z = self.filt_ang
        twist.linear.x = self.filt_lin

        # 转向降速：转得越猛，走得越慢，减少侧滑打滑
        if self.max_angular > 0:
            ratio = abs(twist.angular.z) / self.max_angular
            twist.linear.x *= max(0.0, min(1.0, 1.0 - self.turn_slowdown * ratio))

        # 避障层（最高优先级）：前方有障碍时约束前进，不影响转向/后退
        if self.min_front > 0 and twist.linear.x > 0:
            if self.min_front < self.stop_dist:
                twist.linear.x = 0.0
            elif self.min_front < self.slow_dist:
                factor = (self.min_front - self.stop_dist) / (self.slow_dist - self.stop_dist)
                twist.linear.x *= max(0.0, min(1.0, factor))

        self.cmd_pub.publish(twist)


if __name__ == '__main__':
    try:
        PersonFollower()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
