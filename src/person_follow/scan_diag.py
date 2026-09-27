#!/usr/bin/env python3
# encoding: utf-8
"""
雷达角度诊断脚本：判断 /scan 的 0° 是否对齐车头正前方。
用法（先启动雷达，再把障碍物/纸箱放到车正前方约 0.5 米）：
  python3 scan_diag.py

看输出里的「最近障碍 @ 多少度」：
  - 若接近 0°（±5°内），说明 offset 正确，避障的"前方"判断没问题。
  - 若偏到 16° 或其它角度，说明 wheeltec_lidar.launch 里的 offset 没调准，
    需要把 offset 改成 (0 - 偏的那个角度) 之类，再重启雷达。
"""

import math

import rospy
from sensor_msgs.msg import LaserScan


def cb(msg):
    n = len(msg.ranges)
    inc = msg.angle_increment
    amin = msg.angle_min

    best = None  # (dist, angle_deg)
    for i, v in enumerate(msg.ranges):
        if math.isfinite(v) and v > 0.05:
            ang = math.degrees(amin + i * inc)
            if best is None or v < best[0]:
                best = (v, ang)

    c = int(round((0.0 - amin) / inc))
    front = msg.ranges[c] if 0 <= c < n else -1.0

    if best is None:
        print('前方0°=%.2fm | 未检测到任何障碍' % front)
    else:
        print('前方0°=%.2fm | 最近障碍=%.2fm @ %.0f°' % (front, best[0], best[1]))


if __name__ == '__main__':
    rospy.init_node('scan_diag')
    rospy.Subscriber('/scan', LaserScan, cb)
    rospy.loginfo('把障碍物放车正前方 0.5m，观察下面输出的角度 ...')
    rospy.spin()
