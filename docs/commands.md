# 常用运行命令

本文整理本项目实际使用过的 ROS 命令。除特别说明外，命令在 Ubuntu 20.04 + ROS Noetic 小主机上执行；RViz 通常在笔记本端执行。

## 环境

```bash
source /opt/ros/noetic/setup.bash
source ~/catkin_ws/devel/setup.bash
```

## 底盘、雷达和建图

```bash
# 底盘
roslaunch turn_on_wheeltec_robot turn_on_wheeltec_robot.launch

# Camsense X1 雷达
roslaunch turn_on_wheeltec_robot wheeltec_lidar.launch

# gmapping 建图
roslaunch turn_on_wheeltec_robot mapping.launch

# 保存地图
rosrun map_server map_saver -f ~/maps/room_map
```

笔记本端可运行：

```bash
rviz -d ~/camsense_view.rviz
```

## 键盘控制

```bash
roslaunch wheeltec_robot_rc keyboard_teleop.launch
```

常用按键：`i` 前进、`,` 后退、`j` 左转、`l` 右转，空格或 `k` 立即停车；`Ctrl+C` 退出。

## 单点导航

```bash
roslaunch turn_on_wheeltec_robot navigation.launch \
  map_file:=/home/feiyv/maps/room_map_v2.yaml
```

笔记本端连接小主机时，根据现场网络修改以下地址：

```bash
export ROS_MASTER_URI=http://192.168.1.100:11311
export ROS_IP=192.168.1.101
rviz -d ~/camsense_view.rviz
```

## 多点导航

多点导航是本项目的重点功能，使用 [6-robot/waterplus_map_tools](https://github.com/6-robot/waterplus_map_tools) 提供的航点工具。该插件不是本仓库原创代码，原项目采用 GPL-2.0 许可证；请按原项目许可获取、编译和使用。

先启动导航并加载地图：

```bash
roslaunch turn_on_wheeltec_robot navigation.launch \
  map_file:=/home/feiyv/maps/room_map_v2.yaml
```

加载已有航点：

```bash
rosrun waterplus_map_tools wp_manager \
  _load:=/home/feiyv/room_waypoints.xml
```

在 RViz 中用航点工具添加目标后保存：

```bash
rosrun waterplus_map_tools wp_saver \
  -f /home/feiyv/room_waypoints.xml
```

开始按顺序执行航点：

```bash
rosrun waterplus_map_tools wp_nav_test
```

## 人员跟随

```bash
# 终端 1：底盘
roslaunch turn_on_wheeltec_robot turn_on_wheeltec_robot.launch

# 终端 2：雷达
roslaunch turn_on_wheeltec_robot wheeltec_lidar.launch

# 终端 3：摄像头
rosrun usb_cam usb_cam_node _video_device:=/dev/video0 \
  _image_width:=640 _image_height:=480 \
  _pixel_format:=yuyv _camera_frame_id:=usb_cam

# 终端 4：行人检测
rosrun person_follow person_detect_onnx.py

# 终端 5：跟随控制
rosrun person_follow person_follow.py
```

人员跟随和导航都会向 `/cmd_vel` 发布速度指令，二者不能同时运行；启动前应关闭键盘控制和导航节点，避免多个节点争抢控制权。
