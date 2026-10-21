# 补丁说明

本目录包含本项目对轮趣（WheelTEC）官方源码的**全部修改**，以 patch 形式发布。

Git 仓库正文不直接收录轮趣 ROS 源码；Release 附件 `all_code-v1.0.0.zip` 提供一份已经应用本项目 ROS 修改、并经过本项目验证的源码快照。使用该快照时不要重复应用 `ros-noetic-c30d.patch`。如果从轮趣官方渠道获取对应版本源码，再按本页说明应用补丁即可。

| 补丁 | 应用对象 | 说明 |
|---|---|---|
| `firmware-c30d-r550.patch` | Keil 固件工程 | 基于用户提供的 `R550_C30D(2.0)_Mini小车STM32源码_霍尔编码器_2025.12.26_副本_20260802` 实际工程验证 |
| `ros-noetic-c30d.patch` | ROS Noetic 源码包 | 修改 `turn_on_wheeltec_robot` 功能包 |

应用前建议先用 `git apply --check <补丁>` 验证你的官方源码版本与补丁基线一致；如果官方版本更新导致补丁应用失败，可按 `docs/firmware.md` 中的"文件 + 函数 + 变量"定位信息手工对齐。

## 固件补丁：firmware-c30d-r550.patch

在 Keil 工程根目录执行：

```bash
git apply firmware-c30d-r550.patch    # git apply 对普通目录同样可用
```

涉及文件与内容：

| 文件 | 修改内容 |
|---|---|
| `BALANCE/robot_select_init.c` / `.h` | 差速车型参数适配：减速比 19:1、编码器 11 线、轮距 0.30 m、轮径 65 mm；通过 `Robot_Select()` 的差速分支传入参数 |
| `BALANCE/balance.c` | ROS 控制帧约 300 ms 超时停车、计数器饱和，以及差速车编码器方向修正 |
| `HARDWARE/usartx.c` | 有效 ROS 控制帧清零超时计数，并过滤 JDY-31 的连接状态回显 |
| `USER/WHEELTEC.uvoptx` / `.uvprojx` | Keil 目标芯片改为 STM32F407VET6 等工程配置 |

各参数的具体函数名、变量名定位见 [固件参数配置](../docs/firmware.md)。

## ROS 补丁：ros-noetic-c30d.patch

在 `catkin_ws/src` 下执行，然后回到工作空间根目录编译：

```bash
cd ~/catkin_ws/src
git apply /path/to/ros-noetic-c30d.patch
cd ~/catkin_ws && catkin_make
```

涉及文件与内容：

| 文件 | 修改内容 |
|---|---|
| `urdf/mini_diff_robot.urdf` | mini_diff 差速模型按实车尺寸适配 |
| `src/wheeltec_robot.cpp` | 里程计 `/odom` 的 z 固定为 0（IMU 融合关闭，抑制静止/直行漂移） |
| `launch/include/base_serial.launch` | 串口设备名改用 udev 固定名 `/dev/wheeltec_controller` |
| `launch/include/algorithm_gmapping.launch` | gmapping 参数（`maxUrange`、`particles` 等，见 [软件架构](../docs/architecture.md)） |
| `launch/include/robot_pose_ekf.launch` | EKF 输出 `odom_combined -> base_footprint` |
| `launch/robot_model_visualization.launch` | 机器人模型显示适配 |

## 覆盖范围说明

- 补丁只包含对官方文件的**修改与新增**，不包含删除；官方源码中未被补丁触及的文件按原样使用（包括官方自带的 `waypoint_follower.py`、`waypoints.yaml` 等）。
- Camsense X1 雷达驱动的无效点（质量值 0 → NaN）修复**不在补丁里**——该驱动是 BSD 3-Clause 开源软件，已直接包含在本仓库 `src/camsense_driver/` 中，编译时直接使用即可。
