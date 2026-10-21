# 软件架构与技术总结

本文从整体上描述这台小车的软件组成、TF 坐标链、建图与导航方案，以及调试过程中遇到的关键问题，适合在动手复刻前先通读一遍。各模块的具体操作见 [复刻流程](bringup.md) 与 [ROS 环境搭建](ros-setup.md)。

## 1. 项目目标

这个项目的目标是做一台可以独立完成建图、定位、导航和人员跟随的 ROS 小车。小车通过激光雷达建立室内二维地图，保存地图后使用 AMCL 定位和 `move_base` 导航；另外利用车载摄像头识别人，并根据人的位置控制小车跟随。

目前底盘、雷达、远程控制、建图、地图保存、导航和人员跟随的主要链路都已经跑通，已经可以用于演示。建图在转弯和大范围场地中仍有一些重影，属于现在最明显的不足。

## 2. 硬件和软件环境

小车使用 Wheeltec C30D mini_diff 底盘，是两轮差速结构，后面带万向轮。左右驱动轮分别接底盘的 A、B 电机通道，轮距实测约 0.30 m，整车外形约为 0.30 m × 0.33 m。

上位机是 Ubuntu 20.04 和 ROS Noetic 的 x86 小主机，内存 4 GB。底盘通过 USB 串口与小主机通信，底盘发布轮式里程计 `/odom`，实际频率约 20 Hz。雷达使用 Camsense X1，发布 `/scan`，实测每圈 400 个点、约 5.2 Hz、360°扫描，量程上限约 8 m。雷达安装在车体前方，当前使用的 TF 大致为 `base_footprint -> laser`，平移约 `(0.12, 0, 0.127)` m，偏航角为 0。

摄像头使用罗技 C930c。人员跟随部分使用 YOLOv8n 模型，先在笔记本上将 `yolov8n.pt` 导出为 320×320 输入的 `yolov8n.onnx`，再把模型放到小主机上运行，避免在没有 AVX/AVX2 的 J3160 上直接运行 PyTorch。

## 3. 系统结构

现在的 TF 主链是：

```text
map -> odom_combined -> base_footprint -> laser
```

其中，底盘提供原始轮式里程计，`robot_pose_ekf` 整理并发布 `odom_combined -> base_footprint`，激光雷达通过静态 TF 连接到车体。建图程序发布 `map -> odom_combined`；进入导航后停止建图程序，改由 AMCL 发布这段 TF。

软件上主要由以下几部分组成：

- `wheeltec_robot`：底盘串口通信、速度控制、里程计和 IMU 数据发布。
- `camsense_driver`：读取 Camsense X1，并发布 `/scan`（见 `src/camsense_driver/`，含无效点 NaN 修复）。
- `robot_pose_ekf`：目前主要使用轮式里程计生成连续的底盘 TF。
- `slam_gmapping`：当前建图主线，使用激光扫描和里程计完成二维 SLAM。
- `slam_toolbox`：曾安装并实车测试过的历史对照方案，更新速度较快；当前项目建图使用 `gmapping`，不把历史方案写成已验证的当前回退配置。
- `map_server`、`amcl`、`move_base`：加载已保存地图、定位和自主导航。
- [Waterplus 地图工具](https://github.com/6-robot/waterplus_map_tools)：本项目多点导航的核心插件，负责保存和读取航点。Release 的 ROS 快照中包含该插件，并保留其 GPL-2.0 许可证；Git 仓库正文只记录调用方式和补丁。
- YOLOv8n + ONNX/OpenCV：人员检测和跟随（见 `src/person_follow/` 与 [人员跟随](person-follow.md)）。

## 4. 已完成的底盘和 ROS 联调

底盘串口、雷达串口和远程 SSH 已经打通。为了避免设备名随插拔变化，底盘和雷达使用了固定的 udev 名称。键盘可以通过 `/cmd_vel` 控制小车，前进、后退、原地转弯和停车方向已经核对过。

编码器方向曾经与原始程序的假设相反，已经在差速车型对应的编码器符号处修正，否则闭环会出现越控越快的正反馈。底盘还增加了控制帧丢失后的自动停车逻辑，断开控制端后小车可以在很短时间内停下。

里程计做过直行和旋转校准，当前使用过的修正系数包括：

```text
odom_x_scale = 1.022
odom_y_scale = 1.0
odom_z_scale_positive = 1.019
odom_z_scale_negative = 1.019
```

这些数值是实车校准结果，不是直接照搬四轮或麦克纳姆底盘的参数。

## 5. 建图过程和主要问题

早期使用 gmapping 时，曾经出现过激光点云和地图对不上、转弯重影以及运动后地图更新滞后的现象。期间测试过粒子数、迭代次数、扫描跳点、最大量程、地图分辨率等参数，也对比过 `slam_toolbox`。`slam_toolbox` 的异步处理和回环效果较好；当前项目继续使用 gmapping，slam_toolbox 作为历史对照记录。

目前 gmapping 测试中使用过的主要参数是：`maxRange=8`、`maxUrange=6`、`particles=20`、`iterations=5`、`lskip=2`，地图分辨率曾试过 0.1 m。实际参数以启动后通过 `rosparam get /slam_gmapping/...` 查到的结果为准。

后面定位到一个影响很大的雷达数据问题。Camsense 驱动把质量为 0 的无效回波直接发布成 0 m，gmapping 会把这些数据当成近距离障碍，结果是在车周围形成一个会随车移动的大白色圆盘。现在已经把无效回波改成 `NaN`，测试时 0 值已经从约 180 个降为 0，地图中的移动圆盘也消失了。

这个修复说明之前的异常不完全是 gmapping 参数造成的。当前仍然存在一个容易误解的地方：`maxUrange=6` 只表示算法最多使用 6 m 的有效数据，并不代表所有方向都会自动建到 6 m。雷达对深色、玻璃、远距离或低反射物体可能返回无效值，因此实际地图范围会小于设置的最大量程。

现在建图时直行基本能够跟上，转弯仍然更容易出现重影。原因主要和雷达频率较低、差速底盘转弯打滑、转弯时相邻扫描之间位姿变化较大有关。后续如果还有时间，优先做雷达安装角度复核、轮距和旋转里程计复核，再单独调整 gmapping 噪声参数；不再同时修改多个参数。

## 6. 地图保存和自主导航

建图完成后使用 `map_saver` 保存地图，得到同名的 `.pgm` 和 `.yaml` 文件。例如：

```bash
rosrun map_server map_saver -f ~/maps/room_map
```

导航时先停止 `slam_gmapping` 或 `slam_toolbox`，然后启动底盘、雷达、地图服务器、AMCL 和 `move_base`。导航期间不能同时让 SLAM 和 AMCL 发布 `map -> odom_combined`，否则 TF 会冲突。

RViz 在笔记本上运行，小主机负责 ROS 节点。RViz 的 Fixed Frame 使用 `map`，先用 `2D Pose Estimate` 设置初始位姿，再使用 `2D Nav Goal` 发送目标点。单点导航通过后，再进行多个目标点连续导航。航点工具已经在笔记本端编译，保存的 `room_waypoints.xml` 可以交给 Waterplus 的航点导航节点读取。

当前导航链路已经可以用于基础演示，后续重点是根据实际车体尺寸继续核对 footprint、代价地图膨胀半径和转弯速度。

## 7. 人员跟随

人员跟随使用罗技 C930c 摄像头采集图像，YOLOv8n 只检测 `person` 类别。由于小主机 CPU 不支持 AVX/AVX2，没有在小主机上安装完整的 PyTorch/Ultralytics 运行环境，而是在笔记本上完成模型导出：

```text
yolov8n.pt -> yolov8n.onnx
输入尺寸：320×320
ONNX opset：12
模型文件：约 13 MB
```

小主机侧使用 ONNX/OpenCV 进行推理，再根据检测框中心相对图像中心的偏差控制转向，根据目标框大小估计人与车的距离，输出 `/cmd_vel`。雷达和底盘速度控制仍然保留，跟随过程中以低速为主，并在目标丢失或前方存在障碍时停车。

人员检测和跟随功能目前已经完成，可以进行演示。它的速度和稳定性主要受小主机 CPU、摄像头帧率、光照以及人与车之间遮挡情况影响。实现细节与调参见 [人员跟随](person-follow.md)。

## 8. 当前状态和不足

目前已经具备以下能力：

- 远程启动底盘、雷达和 ROS 节点；
- 键盘控制小车并发布轮式里程计；
- 使用激光雷达建二维地图；
- 保存地图并通过 AMCL 定位；
- 使用 `move_base` 完成单点和多点导航；
- 读取航点文件执行连续导航；
- 通过摄像头和 YOLOv8n 完成人员检测跟随。

还没有完全解决的问题主要有三个：大场地建图时有效雷达回波范围偏小，转弯时偶尔有重影，以及小主机无线网络距离较远时可能掉线。这些问题不影响当前基本演示，但会影响地图精度、导航连续性和远程操作体验。对应的排查思路见 [故障排查](troubleshooting.md)。

## 9. 常用命令

下面命令默认在小主机端执行，启动前先确认没有重复运行旧节点：

```bash
source /opt/ros/noetic/setup.bash
source ~/catkin_ws/devel/setup.bash

# gmapping 建图
roslaunch turn_on_wheeltec_robot mapping.launch

# 历史对照：slam_toolbox 建图（非当前项目方案）
roslaunch turn_on_wheeltec_robot slam_toolbox_mapping.launch

# 保存地图
rosrun map_server map_saver -f ~/maps/room_map

# 使用已保存地图启动导航
roslaunch turn_on_wheeltec_robot navigation.launch map_file:=~/maps/room_map.yaml
```

笔记本端主要运行 RViz，并通过 `ROS_MASTER_URI` 连接小主机。人员跟随节点和摄像头相关命令见 [人员跟随](person-follow.md)；运行前要确认没有同时启动键盘控制节点，避免多个节点同时向 `/cmd_vel` 发命令。

## 10. 后续安排

当前优先保持已经能稳定演示的配置，不再大范围改动。后续有时间时，按下面顺序继续优化：

1. 复核激光雷达安装位置、方向和有效回波数据。
2. 用固定距离和固定角度重新标定轮径、轮距和里程计。
3. 在相同路线下比较 gmapping 的转弯速度、噪声参数和分辨率，每次只改一项。
4. 检查导航 footprint 与真实车体外形，补做窄道和动态障碍测试。
5. 优化人员跟随的目标丢失、障碍物急停和断网停车逻辑。

这套系统现在已经不是"只把节点启动起来"的状态，而是完成了从底盘通信、传感器、建图、定位、导航到人员跟随的一整套联调。剩下的问题主要是实车传感器和机械结构带来的精度问题，需要通过实测继续收敛。
