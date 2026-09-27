# ROS 联调准备

本文是小车 ROS 上位机的完整搭建与联调手册：从安装 Ubuntu 20.04 与 ROS Noetic 开始，到串口权限与 udev 固定名称、底盘与雷达驱动编译，再到建图、地图导航和键盘遥控的完整启动流程。按顺序操作，即可在一台全新的 Ubuntu 小主机上复刻整套软件环境并跑通建图导航。

> 项目当前建图使用 `gmapping`，保存地图后用 AMCL + `move_base` 导航，多点导航和人员跟随已完成基本演示。`slam_toolbox` 作为历史对照方案保留。

目标：让 Ubuntu 上位机通过 **USART3** 控制 C30D 底盘，打通 `键盘/ROS → /cmd_vel → 底盘驱动 → STM32 → 电机`，并收到编码器里程计 `/odom` 和 TF（`odom_combined → base_footprint`），完成 ROS 建图、地图导航和多点导航。

## 一、开始前先确认三件事

1. Ubuntu 小主机能开机进系统、**能联网**？（ROS 安装需要联网下载，约 1~2GB）
2. ROS Noetic 是否已安装？（未装按第二部分装）
3. **C30D 的 ROS 底盘驱动包**：驱动源码的获取方式见仓库 README；协议与固件 USART3（115200、8N1、无流控）一致（固件解析见 [固件参数配置 · USART3 和备用串口](firmware.md#usart3-和备用串口)），配置步骤见第四节。

## 二、安装 Ubuntu 20.04 + ROS Noetic

> 若系统不是 Ubuntu 20.04 或 ROS 已装，跳过对应步骤。

### 2.1 检查系统版本

```bash
lsb_release -a
```

必须是 `Ubuntu 20.04.x`（ROS Noetic 只支持 20.04）。

### 2.2 换软件源（国内建议清华/阿里，下载快）

用清华源示例（按官方镜像站步骤操作）：备份原源 → 写入清华源 → `sudo apt update`。具体以 [清华 TUNA 镜像站](https://mirrors.tuna.tsinghua.edu.cn/help/ubuntu/) 当前指引为准。

### 2.3 安装 ROS Noetic（官方步骤）

```bash
sudo sh -c "echo deb http://packages.ros.org/ros/ubuntu $(lsb_release -sc) main > /etc/apt/sources.list.d/ros-latest.list"

# 添加密钥
sudo apt install curl
curl -s https://raw.githubusercontent.com/ros/rosdistro/master/ros.asc | sudo apt-key add -

# 更新并安装（时间较长，约 1~2GB）
sudo apt update
sudo apt install ros-noetic-desktop-full
```

初始化 rosdep：

```bash
sudo rosdep init
rosdep update
```

配置环境变量：

```bash
echo "source /opt/ros/noetic/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

验证：

```bash
roscore
```

能启动、Ctrl+C 退出即成功。

### 2.4 创建 catkin 工作空间

```bash
mkdir -p ~/catkin_ws/src
cd ~/catkin_ws
catkin_make
echo "source ~/catkin_ws/devel/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

## 三、串口权限与 udev 固定名称

### 3.1 加入 dialout 组（免 sudo 打开串口）

```bash
sudo usermod -a -G dialout $USER
```

**必须重新登录**（或重启）才生效。

### 3.2 查看设备

```bash
ls -l /dev/ttyUSB*
dmesg | tail -30
```

插拔分别观察，确认哪个是底盘串口（USART3 经 USB 转 TTL）、哪个是雷达。

### 3.3 写 udev 规则（固定名称，防 ttyUSB0/1 互换）

```bash
# 查 USB 转串口芯片的 idVendor/idProduct
udevadm info -a -n /dev/ttyUSB0 | grep -E "idVendor|idProduct"
```

新建 `/etc/udev/rules.d/99-ros-car.rules`，把 `xxxx`/`yyyy` 换成上面查到的值：

```text
SUBSYSTEM=="tty", ATTRS{idVendor}=="xxxx", ATTRS{idProduct}=="yyyy", SYMLINK+="wheeltec_controller", MODE="0666"
```

雷达同理设成 `camsense_x1`。完成后：

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

拔插后应出现 `/dev/wheeltec_controller`、`/dev/camsense_x1`。**launch 文件只用固定名，不依赖 /dev/ttyUSB0**（参见 [硬件与接线 · USB 和串口分工](hardware.md#usb-和串口分工)）。

## 四、C30D 底盘驱动（官方源码 + patches 补丁）

> **驱动包来源**：`camsense_driver` 与 `person_follow` 已包含在本仓库 `src/` 下（分别为 BSD 3-Clause 与 MIT）；`turn_on_wheeltec_robot` 与 `wheeltec_robot_rc` 需获取轮趣官方 Noetic 源码后，应用本仓库 `patches/` 目录中的补丁，详细获取步骤见 README。
> **Ubuntu 软件配置**：依赖 7 包已装、ROS 源切清华镜像、`catkin_make` 0 报错（已在 CMakeLists 中补上 `add_dependencies`，包含在补丁内）、`.bashrc` 已 source、dialout 已生效。
> **底盘联调结果**：udev 固定 `/dev/wheeltec_controller`（CH9102，ttyACM0）与 `/dev/camsense_x1`（CH340，ttyUSB0，须直连 USB 不能过拓展坞）；`/odom` 稳定 20Hz；`/scan` 约 5.2Hz/360°/400 点；键盘四向一致。早期记录过"松手约 0.3s 停车、滑行 4~6cm"，但没有注明当时采用的控制链路，不能据此认定 ROS/UART3 通信中断停车已通过；该项验证见 [固件参数配置 · ROS 通信超时停车](firmware.md#ros-通信超时停车)。后续已完成激光 TF、里程计校准、gmapping 建图和导航基本演示；slam_toolbox 是历史对照。

1. **拷贝到 Ubuntu**：把官方源码中的 `turn_on_wheeltec_robot`、`wheeltec_robot_rc` 和本仓库 `src/` 下的 `camsense_driver`、`person_follow` 放进 `~/catkin_ws/src/`（复制或软链接均可）。拷完先补脚本执行权限：`chmod +x ~/catkin_ws/src/*/scripts/*.py ~/catkin_ws/src/person_follow/*.py`（Windows 拷过去的文件没有 x 权限）。
2. **补丁已包含的配置修改**（应用 `patches/` 后无需手动再改）：
   - `car_mode=mini_diff`（C30D 两轮差速，原默认 `senior_akm` 不适合）；
   - `wheeltec_lidar.launch` 已整体换成 Camsense X1 驱动（原文件备份为 `.orig.bak`）；
   - `mapping.launch` 已注释 `world_canvas_msgs` 保存节点（省一个依赖，保存地图用 `map_saver`）；
   - `amcl.launch` 里程计模型改为 `diff-corrected`（差速车定位更准）；导航前仍需核对其实际 frame 参数。
   - 改动明细见 `patches/` 内的补丁说明。
3. **装系统依赖**（需联网，一次性）：

```bash
sudo apt update
sudo apt install ros-noetic-navigation ros-noetic-gmapping ros-noetic-slam-toolbox ros-noetic-teb-local-planner ros-noetic-robot-pose-ekf ros-noetic-serial ros-noetic-joy ros-noetic-teleop-twist-keyboard
```

4. **核对协议**：驱动串口为 **115200、8N1、无流控**，与固件 USART3 一致（`base_serial.launch` 里 `serial_baud_rate=115200` 已符合，无需改）。
5. **串口名**：驱动默认读 `/dev/wheeltec_controller`；雷达 launch 用 `/dev/camsense_x1`。官方 `wheeltec_udev.sh` 已含 CP2102/CH9102 规则（按 USB 串口号 0002 命名 `wheeltec_controller`）；本车控制板实际串口芯片需在 Ubuntu 上 `lsusb` 确认，把 `idVendor/idProduct` 写进 udev 固定成这两个名字（步骤见本文第三节和 README）。
6. **编译**：

```bash
cd ~/catkin_ws
catkin_make
source devel/setup.bash
```

7. **启动并验证**：

```bash
roslaunch turn_on_wheeltec_robot turn_on_wheeltec_robot.launch
# 另开终端：
rostopic echo /odom
rqt_graph
```

底盘单独启动时，预期底盘节点订阅 `/cmd_vel`、发布 `/odom`，并由项目 EKF 整理为当前实车链中的 `odom_combined → base_footprint` TF。若只看到官方示例的 `odom → base_link`，不要直接用于导航，先核对实际 launch 和 `rosrun tf tf_echo odom_combined base_footprint`。

### 4.1 雷达 Camsense X1（官方不支持，本仓库已内置驱动）

- 官方 `wheeltec_lidar.launch` 只支持镭神 M10/N10、乐动 LD14/LD19、思岚 A1/A2/A3/S1 和 16 线 LS_CX，**没有 Camsense X1**，其协议也不兼容 `rplidar_ros`。
- 本仓库 `src/camsense_driver/` 已内置开源 ROS1 驱动（BSD 3-Clause）：节点 `camsense_publisher`、发布 `/scan`、frame_id=`laser`、参数 `port`/`offset`。
- 端口用 udev 固定为 `/dev/camsense_x1`（launch 已用此名）。`offset=16.0` 为角度偏移初值，装车后按 `/scan` 与车头对照微调。
- **已核定的 TF 值**：mini_diff 原默认值与本车安装位姿不一致。已改为 `base_footprint → laser`：x=0.12、y=0、z=0.127、yaw=0，`offset=16.0`；现场最终值以 `rosrun tf tf_echo base_footprint laser` 为准。不要恢复原默认的 yaw=π 或 z=0.10992。
- 完成后对照 [复刻流程 Bringup · Camsense X1 的 Noetic 兼容检查](bringup.md#camsense-x1-的-noetic-兼容检查) 逐项检查。

### 4.2 官方资料常用命令速查

| 功能 | 命令 |
|---|---|
| 键盘遥控 | `roslaunch wheeltec_robot_rc keyboard_teleop.launch` |
| 2D 建图（当前方案 gmapping） | `roslaunch turn_on_wheeltec_robot mapping.launch` |
| slam_toolbox 在线建图（历史对照） | `roslaunch turn_on_wheeltec_robot slam_toolbox_mapping.launch` |
| 2D 导航（AMCL+move_base，含多点 `send_mark.py`） | `roslaunch turn_on_wheeltec_robot navigation.launch` |
| 保存地图 | `rosrun map_server map_saver -f ~/map` |

里程计线性/角度修正用 `base_serial.launch` 里的 `odom_x_scale` / `odom_z_scale_positive` / `odom_z_scale_negative`（实测直行/转向误差后调，不必改固件）。

## 五、从已保存地图开始导航

以下命令均在**小主机端**执行；笔记本只负责本地 RViz 显示和发送目标。导航前必须先关闭建图终端（`slam_toolbox`/`slam_gmapping`），确保不再发布 `map → odom_combined`。

### 5.1 小主机端启动

```bash
source /opt/ros/noetic/setup.bash
source ~/catkin_ws/devel/setup.bash

# 先查看项目 launch 将启动哪些节点
roslaunch --nodes turn_on_wheeltec_robot navigation.launch

# navigation.launch 已包含底盘、雷达、map_server、AMCL 和 move_base
roslaunch turn_on_wheeltec_robot navigation.launch map_file:=/home/robot/maps/room_map.yaml
```

不要再单独启动 `turn_on_wheeltec_robot.launch`、`wheeltec_lidar.launch`、`map_server` 或 `amcl.launch`，否则会重复启动。现场必须确认导航配置采用 `odom_combined`、`base_footprint` 和 `laser`，不能直接套用官方示例的 `odom`、`base_link`。如果 `map_file` 覆盖不生效，再改用拆分启动方案，并逐项核对节点名。

核对命令：

```bash
rosnode list
rosnode info /amcl
rosnode info /move_base
rosrun tf tf_echo map odom_combined
rosrun tf tf_echo odom_combined base_footprint
rostopic hz /map
rostopic echo -n 1 /amcl_pose
```

预期：只有 AMCL 发布 `map → odom_combined`；底盘/EKF 发布 `odom_combined → base_footprint`；静态 TF 发布 `base_footprint → laser`；`/map` 来自 map_server 且不再由 SLAM 更新。

### 5.2 笔记本端 RViz

笔记本本地运行 `rviz -d ~/camsense_view.rviz`（或打开已有 RViz 配置），Fixed Frame 设为 `map`。添加/确认 Map、LaserScan(`/scan`)、TF、RobotModel、AMCL Pose。点击 `2D Pose Estimate` 设置初始位置，等激光墙线与地图重合后，再点击 `2D Nav Goal` 发送目标。

### 5.3 导航验证顺序

先在车周围清空、速度保持低速：

1. 起点附近 0.5~1m 单点，确认能规划、到点后停车。
2. 直线和 L 形路线，观察定位是否持续贴合地图。
3. 发送 3~5 个目标点，检查连续导航、转弯和恢复行为。
4. 最后测试窄道、临时障碍物和取消目标；任何碰撞或失控立即按急停/断电。

导航问题先记录 `/amcl_pose`、TF、代价地图和 `move_base` 日志；不要在未确认 TF 唯一性前盲调 TEB/DWA。

## 六、键盘控制（teleop_twist_keyboard）

建图时**手动开车**就用它（也是联调测试工具）。

```bash
sudo apt install ros-noetic-teleop-twist-keyboard
```

> 官方源码包 `wheeltec_robot_rc` 自带键盘遥控 `roslaunch wheeltec_robot_rc keyboard_teleop.launch`（见 4.2），`teleop_twist_keyboard` 可作备选。

运行（在底盘节点已启动的前提下）：

```bash
rosrun teleop_twist_keyboard teleop_twist_keyboard.py
```

常用键（按终端提示）：

| 键 | 动作 |
|---|---|
| `i` / `,` | 前进 / 后退 |
| `j` / `l` | 左转 / 右转 |
| `u` `o` `m` `.` | 斜向 |
| `k` | 停 |
| `q` / `z` | 加速 / 减速（0.2 步进） |

**首次测试前先确认**：遥控降速已设置（`RC_Velocity` 建议 300）；车轮悬空；速度从最低开始。

## 七、联调测试与验证

本节对应 [复刻流程 Bringup · 阶段 5：ROS 底盘联调](bringup.md#阶段-5ros-底盘联调)。按顺序做，一项不过不进入下一项：

1. **/cmd_vel 控制**：键盘/命令行发 `rostopic pub`，确认直行、后退、原地转向方向正确。
2. **300ms 断联停车**：运动中停止发布 `/cmd_vel`（或拔数据线），实测车轮约 300ms 内停下；恢复发布后不得无命令自行继续。（固件逻辑见 [固件参数配置 · ROS 通信超时停车](firmware.md#ros-通信超时停车)）
3. **直行误差**：`cmd_vel` 直行 1~2m，量实际距离 → 记录误差 → 校**有效轮径**。
4. **旋转误差**：原地转 360°，量实际角度 → 记录误差 → 校**轮距**。
5. **TF 唯一性**：`rqt_tf_tree` 检查当前实车链 `map → odom_combined → base_footprint → laser` 每段只有一个发布者、时间戳单调。
6. **持续运行**：连续 20 分钟无失控/断连。

每次测试建议按 [复刻流程 Bringup 的试车记录模板](bringup.md#每次试车记录模板) 做好记录。

## 八、供电整合备忘

- 测试阶段：主机用原装 12V/3A 适配器，C30D 用电池，隔离电机干扰。
- 合并供电：电池并联分两支路（C30D 一路、主机一路），各有保险、共受总开关，参见 [硬件与接线 · 推荐整车供电拓扑](hardware.md#推荐整车供电拓扑)。
- 直连/升降压决定：先测主机允许输入范围 + 电池完整电压范围 + 电机启动干扰，参见 [硬件与接线 · 主机支路如何决定](hardware.md#主机支路如何决定)。
- 合并后必须复测：电机启停不使主机重启、串口不掉线、雷达不断流。

## 九、故障排查速查

- 串口打不开 → 权限（dialout）、端口占用、udev 名称（见 [故障排查与备选方案 · 雷达驱动编译或运行失败](troubleshooting.md#雷达驱动编译或运行失败)）。
- 底盘无响应 → 先确认驱动与固件波特率一致；用串口工具直接对 USART3 看帧（见 [故障排查与备选方案 · C30D 的 UART3 接口与预期不符](troubleshooting.md#c30d-的-uart3-接口与预期不符)）。
- 直行跑偏 → 校轮径/`LineDiffParam`；旋转角度错 → 校轮距（见 [故障排查与备选方案 · 导航抖动、绕圈或撞障碍](troubleshooting.md#导航抖动绕圈或撞障碍)）。

---

相关文档：[硬件与接线](hardware.md) · [固件参数配置](firmware.md) · [复刻流程 Bringup](bringup.md) · [故障排查与备选方案](troubleshooting.md) · [软件架构](architecture.md)  
资料来源：ROS Noetic 官方安装文档、轮趣官方协议资料
