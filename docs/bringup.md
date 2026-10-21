# 分阶段实施与验证清单

本文把这台差速导航小车从收到零件到完成建图、定位与 `move_base` 导航的整个过程拆成阶段 0～6，每个阶段给出检查项和通过标准：前一阶段未达标，不进入下一阶段。适合想复刻同款小车的读者照单执行；已勾选的条目表示已在实车上验证通过，未勾选的是可选增强项或需按你的实际情况完成的项。

> 当前状态（2026-09）：底盘与 ROS 联调、gmapping 建图、保存地图后的 AMCL + `move_base` 导航、多点导航、人员跟随均已完成基本实车演示。多点导航有一次约 2 分 42 秒、无碰撞的实测记录（项目路线为 4 个锥筒布置）。`slam_toolbox` 已在实车试过，现作为历史对照方案保留。转弯重影仍是已知不足。

## 阶段 0：底板未到时的准备

这一步在硬件到手前做齐备份、工具和资料核对。做到"原始资料有备份、工具和电源信息齐全、台架方案可行"即通过。

- [x] 保留原始压缩包、原工程和 `OBJ\WHEELTEC.hex`，复制工程副本后再修改（备份目录 `_副本_20260802`，未修改）
- [ ] 准备万用表、保险丝/座、总开关、压线钳、热缩管和急停手段
- [ ] 向主机商家确认 5525 接口的最低/最高允许输入电压；中心正极已有适配器实物依据，但接线前仍复测
- [ ] 电池充满后用万用表记录电压，不以充电器 12.6V 代替电池端实测
- [ ] 可在 Ubuntu 20.04/Noetic 中完成雷达驱动编译和 `/scan` 验货
- [x] 核对 Keil 目标设备并在工程副本中准备参数宏，但不填写虚构轮距/轮径（DIFF 宏已建好占位）
- [x] 可将两台电机固定在临时木板/亚克力板上做悬空台架（实际由整车悬空台架替代）
- [x] 首次上电前暂不覆盖 C30D 出厂固件（先验证基础功能，之后再烧录自编译固件）

通过标准：原始资料有备份；工具和电源信息已登记；所有台架运动测试均能固定电机且让轮子悬空。

## 阶段 1：机械安装与尺寸实测

这一步完成机械安装，并把导航所需的全部几何尺寸实测记录下来。轮距、左右轮有效轮径、车体 footprint 和雷达安装位姿都有带单位的实测记录即通过。

- [x] 两驱动轮同轴、平行、固定牢靠
- [x] 两万向轮均匀着地，不抬起驱动轮或造成车身明显摇摆
- [ ] 电池低且靠近中心；主机、C30D、雷达固定且便于散热/插拔
- [x] 雷达水平、无遮挡，并记录相对 `base_link` 的 x/y/z/yaw（粗测完成）
- [x] 测左右驱动轮接地点中心线间距，记录轮距 m（0.30m）
- [ ] 整车承重、无打滑地滚动 5～10 圈，平均周长除以 π 得有效轮径
- [x] 测量底盘含突出物的最大外形，绘制导航 `footprint`（外形 0.30×0.33m 已测；footprint 数值待写入导航配置）

通过标准：轮距、左右轮有效轮径、车体 footprint 和雷达安装位姿都有带单位的实测记录。

## 阶段 2：断电接线

这一步在完全断电状态下完成整车接线并逐线核对。断电检查无短路/反接、每根线都能解释清楚即通过。

- [x] 左轮接 Motor A、右轮接 Motor B，C/D 空置（方向验证通过）
- [x] 按卖家针序图核对动力线、编码器供电和 A/B 相（方向验证通过即接线正确）
- [ ] 电池并联分为 C30D 和主机两支路，各有保险，均受总开关控制
- [ ] 主机支路按 [硬件与接线](hardware.md#主机支路如何决定) 选择直连或转换
- [ ] 测 5525 极性、各电源端对地电阻，排除短路
- [ ] 数据线与电源线分开布置，电机线远离雷达和编码器信号线

通过标准：断电检查无短路/反接；每根线的两端、用途、极性均可解释。

## 阶段 3：悬空电子台架

这一步在车轮不落地的状态下验证电机方向、编码器、车型选择、速度限制和断联停车。任何一项失败都禁止落地。

- [ ] 主机先用原装适配器，C30D 用电池；车轮悬空且急停可达
- [x] 单独低速点动 A、B，确认物理正方向（经 APP 摇杆验证）
- [ ] 编码器精度验证：OLED 自检页（长按板载用户键翻到 3/8 页可看 A+/B+ 实时计数，方法见 [故障排查](troubleshooting.md)）只显示速度/方向、无累计计数，因此改用 ROS 联调直行里程校准来验证（更正说明见 [故障排查](troubleshooting.md#编码器计数不是-836圈)）。也可手转输出轴 10 圈做计数核对：按减速比 19、编码器线数 11、4 倍频，理论值约 8360 计数/10 圈（`11×19×4`），记录数值和正负号；实际计数与理论不符，以故障排查一篇的结论为准
- [x] 给正速度目标时编码器反馈为正，闭环不突然加速（编码器符号已反相修正）
- [x] OLED 选择并显示 `Diff`，不是 `Mec`
- [ ] 测试 `/cmd_vel` 停止、拔数据线后约 300ms 停车
- [ ] 先验证 0.3m/s 左右速度限制，再允许落地

通过标准：方向、计数、车型、速度限制和断联停车全部通过。任何一项失败禁止落地。

## 阶段 4：修改、编译和烧录最终固件

这一步只在工程副本上改参数、编译、烧录，烧完必须把阶段 3 的检查全部复验一遍。

- [x] 仅修改 R550 C30D V2.0 工程副本（原目录保留不动，`_副本_20260802` 为未改备份）
- [x] Keil 目标改为 STM32F407VET6 / 512KB Flash，并全量编译（FLM 算法仍为 1MB，不影响 FlyMcu，用 Keil 直接下载前需补）
- [x] 差速分支使用减速比 19、编码器线数 11、倍频 4（DIFF_GEAR_RATIO/DIFF_ENCODER_LINES 宏）
- [x] 写入承重实测轮径和左右轮距（轮距 0.30 已写入；轮径暂用标称 0.065，待承重实测后更新）
- [x] 保留 `Diff` 实体选择，排障时才临时强制 `Diff_Car`
- [x] 恢复/实现约 300ms 通信超时停车，计数器饱和防溢出（代码已实现，待 UART3/ROS 联调实测）
- [ ] 台架速度限幅约 0.3m/s
- [x] 编译零错误、固件不超过 512KB，记录编译时间和文件哈希（215618B，MD5 8D1A9F18...）
- [x] 通过 UART1 + CH9102 + FlyMcu 烧录，烧后重新执行阶段 3（烧后方向/闭环已复验）

### 固件里的两个可选安全参数（默认保持原值）

这两处都位于轮趣 R550 C30D V2.0 STM32 工程的 `BALANCE/balance.c`，属于可选安全项，当前固件保持默认值，不需要重编译重烧。如需改动：用 Keil 重新编译（0 Error），用 FlyMcu **全片擦除**后烧录（擦掉 Flash 旧参数，新默认值才生效），烧完重新复验阶段 3。

1. **降速（蓝牙/APP 遥控默认速度）**：第 72 行 `RC_Velocity = 500;` → 可改 `300`。APP 有加减速键（X/Y）可随时覆盖默认速度；实测 500 的默认速度并不算快，故保持 500，日后嫌蓝牙默认速度快再改。
2. **台架速度限幅（所有控制，含 ROS）**：第 108 行 `float amplitude=3.5;` → 可改 `0.3`（单位 m/s）。蓝牙速度由 RC_Velocity + APP 加减速控制，不受它影响；它只管所有命令（含 ROS）的**上限**。建议在 ROS 首次联调测试前临时改 0.3 兜底测一轮，之后再调大，并同时在 ROS `move_base` 里限速（见 [固件参数配置](firmware.md#速度限幅和编码器方向)）。

通过标准：新固件可回溯到工程副本和参数记录；烧后阶段 3 全部复验通过。

## 阶段 5：ROS 底盘联调

这一步让 ROS 节点通过串口稳定控制底盘，并把直行和原地旋转的里程计误差校准掉。做到连续运行 20 分钟以上无失控/断连即通过。详细操作步骤（Ubuntu/ROS 安装、驱动、键盘控制、测试命令）见 [ROS 环境搭建](ros-setup.md)。

> 文中的 `turn_on_wheeltec_robot`、`wheeltec_robot_rc` 可以使用 Release 的 `all_code-v1.0.0.zip` 快照；也可以使用轮趣官方 Noetic 源码并应用本仓库 `patches/` 目录的补丁（获取步骤见 README）。Camsense X1 驱动已包含在仓库 `src/camsense_driver/`。

- [x] Ubuntu 20.04.6、ROS Noetic 和 C30D 底盘节点正常启动
- [x] USART3 为 115200、8N1，固定为 `/dev/wheeltec_controller`
- [x] `/cmd_vel` 可控制直行、后退、原地转向，停止发布后安全停车
- [x] 静止里程计不持续跑，直行误差已通过 `odom_x_scale=1.022` 修正
- [x] 原地旋转误差已通过正/反向 `odom_z_scale=1.019` 修正
- [x] 建立唯一 TF 链：`odom_combined → base_footprint → laser`；每段 TF 只允许一个发布者
- [ ] 合并整车电源后，电机启停不使主机重启或串口掉线

通过标准：连续运行至少 20 分钟无失控/断连；直行和旋转误差已量化，且知道下一次校准改哪个参数。

## Camsense X1 的 Noetic 兼容检查

这一步单独核对雷达驱动在 Noetic 下的编译、话题质量和热插拔行为。连续 30 分钟 `/scan` 稳定即通过。

- [ ] 系统为 Ubuntu 20.04 x86，ROS 发行版为 Noetic
- [x] 包直接位于 `catkin_ws/src/camsense_driver`（编译通过）
- [ ] 安装 `catkin`、`roscpp`、`std_msgs`、`sensor_msgs`、Boost、RViz，并运行 `rosdep install --from-paths src --ignore-src -r -y`
- [ ] 确认它是 C++/`roscpp` 节点；Noetic 工具链和辅助脚本使用 Python 3，不花时间移植不存在的 Python 2 驱动节点
- [ ] 修正 `CMakeLists.txt` 安装目录：实际为 `launch config`，不是 `launch rviz`
- [ ] `catkin_make` 或 `catkin build` 零错误；新终端能 `source devel/setup.bash`
- [ ] 将当前用户加入 `dialout` 组，重新登录后无需 `sudo` 即可打开雷达串口
- [x] 用 udev 固定为 `/dev/camsense_x1`、`/dev/wheeltec_controller`（通过；雷达须直连 USB 口，不能过拓展坞）
- [ ] 115200 下 `/scan` 与 `/rpms` 持续发布；`rostopic hz /scan` 稳定，无长时间停顿
- [ ] `/scan` 的 `frame_id=laser`、约 400 点/圈、量程约 0.12～8m；时间戳单调，无 NaN/Inf 泛滥或除零
- [ ] 检查无效距离被写成 0 时，RViz/代价地图是否形成机器人周围假障碍
- [ ] RViz 对墙测试距离合理、扫描方向正确；根据实装调整默认约 16° offset
- [x] 发布唯一的 `base_footprint → laser` 静态 TF，并核对 x/y/z/yaw（现场为 x=0.12、y=0、z=0.127、yaw=0）
- [ ] 运行时拔掉再插回雷达，记录节点是退出、卡住还是恢复；临时可 `respawn="true"`，长期应做异常捕获/自动重连

通过标准：连续 30 分钟 `/scan` 稳定，拔插行为可预期，RViz 几何方向和实物一致，导航代价地图无由 0 值造成的假障碍。

## 阶段 6：建图、定位和 move_base 导航

这一步完成建图、保存地图，再用 AMCL + `move_base` 跑通单点和多点导航。

### 建图与规划选型（含 slam_toolbox 历史对照）

- 当前建图方案：`slam_gmapping`
- 历史对照：`slam_toolbox` 异步在线建图（不能与 `slam_gmapping` 同时启动）
- 定位：`amcl` + 已保存地图
- 全局规划器：`global_planner/GlobalPlanner`
- 局部规划器：`teb_local_planner/TebLocalPlannerROS`（当前 `navigation.launch` 默认启用）
- DWA（`dwa_local_planner/DWAPlannerROS`）保留为独立对照方案；切换前需复制并核对参数，不与 TEB 同时启动

实车 TF 必须形成且不重复发布：

```text
map → odom_combined → base_footprint → laser
```

`slam_gmapping` 或 AMCL 提供 `map → odom_combined`，底盘/EKF 提供 `odom_combined → base_footprint`，静态发布器提供 `base_footprint → laser`。历史 slam_toolbox 对照也使用同一 TF 设计。建图和导航切换时，必须先停止 SLAM，再启动 AMCL，保证 `map → odom_combined` 只有一个发布者。

### 当前建图与地图文件

- 当前建图启动：`roslaunch turn_on_wheeltec_robot mapping.launch`（参数以小主机运行时 `rosparam get /slam_gmapping/...` 为准）。
- 历史对照启动：`roslaunch turn_on_wheeltec_robot slam_toolbox_mapping.launch`；配置：`turn_on_wheeltec_robot/slam_toolbox_config/mapper_params_online_async.yaml`。
- 已保存测试地图：`~/maps/room_map.yaml` 与同名 `.pgm`，分辨率 0.05 m/pixel，尺寸 82×91。
- 保存命令：`rosrun map_server map_saver -f ~/maps/room_map`。
- 历史实测：`slam_toolbox` 更新速度和直行跟随曾明显优于 gmapping；转弯仍可能有重影。该结果作为对照记录；当前项目仍使用 gmapping。

历史建图对照记录（slam_toolbox）：

- 从旧 `slam_gmapping` 切换为 `slam_toolbox` 异步在线建图；当前配置使用 Ceres 求解器、开启回环检测，订阅 `/scan`，坐标系沿用 `map → odom_combined → base_footprint → laser`。
- 当前基线分辨率为 0.05 m，最大激光距离为 8 m，地图发布周期为 1 s；实车观察到地图更新更及时，直行时激光与地图跟随较好，CPU/内存占用明显低于 gmapping。
- Camsense X1 约 5.2 Hz、约 400 点/圈，转弯时仍可能出现重影。这属于当前传感器频率和运动状态下的残余问题，不影响当前基本导航演示。
- 后续优化建议（导航基线稳定后再做）：转弯继续降速并沿已走路线回环；对照测试 `resolution=0.075~0.10 m`、地图发布周期和扫描加入间隔；每次只改一项并重新保存地图。不要在建图和导航同时运行时调参。

### 导航启动顺序（小主机端）

先确认没有运行 `slam_toolbox` 或 `slam_gmapping`。项目现有 `navigation.launch` 已包含底盘、雷达、AMCL 和 `move_base`，优先使用这一条命令：

```bash
source /opt/ros/noetic/setup.bash
source ~/catkin_ws/devel/setup.bash

# 单条命令：底盘、雷达、静态 TF、EKF、map_server、AMCL、move_base
roslaunch turn_on_wheeltec_robot navigation.launch map_file:=~/maps/room_map.yaml
```

启动前可先执行 `roslaunch --nodes turn_on_wheeltec_robot navigation.launch` 查看节点集合。不要再单独启动底盘、雷达、map_server 或 AMCL；导航期间只允许 AMCL 发布 `map → odom_combined`，不能同时保留 `slam_toolbox` 的 TF。若 launch 文件版本不接受 `map_file` 覆盖，再采用"底盘 launch + map_server + amcl + move_base"拆分方式，并确保每个节点只启动一次。

### 笔记本端 RViz 与导航测试

笔记本本地运行 RViz，连接小主机 ROS Master；Fixed Frame 设为 `map`，添加 Map、LaserScan、TF、RobotModel 和 `PoseArray`（AMCL 粒子）。先用 `2D Pose Estimate` 设置初始位姿，确认激光与地图墙线重合，再用 `2D Nav Goal` 发送目标。

测试顺序：近距离单点 → 直线单点 → L 形路线 → 多点连续目标 → 窄道和动态障碍。每次只改变一个参数，先记录是否能定位、是否规划出路径、是否安全停车，再调速度/footprint/代价地图。

### 当前 TEB 起始参数

当前 `navigation.launch` 实际加载 `params_costmap_car/param_mini_diff/teb_local_planner_params.yaml`。实车首次导航先保持该配置，优先验证定位、路径和停车；确认存在振荡或转弯问题后一次只改一个参数。当前源码起点为：线速度上限 0.5 m/s、角速度上限 1.5 rad/s、线加速度 0.2 m/s²、角加速度 0.3 rad/s²，实测时仍应从低速操作。

### DWA 备用起始范围

| 参数 | 建议起点/范围 | 说明 |
|---|---:|---|
| `max_vel_x` | 0.25～0.30 m/s | 第一版低速 |
| `min_vel_x` | 0.0 | 先禁倒车，基线稳定后再开放 |
| `max_vel_theta` | 0.8～1.2 rad/s | 防止原地转向过猛 |
| `min_vel_theta` | 0.2～0.4 rad/s | 需低于实际可克服静摩擦的角速度 |
| `acc_lim_x` | 0.3～0.6 m/s² | 保护供电和机械结构 |
| `acc_lim_theta` | 1.0～2.0 rad/s² | 起始范围 |
| `vx_samples` | 10～20 | 先不过度增加计算量 |
| `vtheta_samples` | 20～40 | 差速车角速度采样 |
| `sim_time` | 1.5～2.5 s | 过短易近视，过长可能保守 |
| `xy_goal_tolerance` | 0.08～0.15 m | 按定位噪声调整 |
| `yaw_goal_tolerance` | 0.10～0.20 rad | 按机械能力调整 |

这些只是安全起点，最终不得超过底盘固件已验证的速度和加速度能力。

### 代价地图起始范围

| 参数 | 建议起点/范围 |
|---|---:|
| 全局 `global_frame` | `map` |
| 局部 `global_frame` | `map`（当前源码配置；切换滚动局部代价地图前再单独验证） |
| `robot_base_frame` | `base_footprint` |
| 全局 `resolution` | 0.05 m |
| 局部 `resolution` | 0.03～0.05 m |
| 局部 `width` / `height` | 2.5～4.0 m |
| 全局 `update_frequency` | 2～5 Hz |
| 局部 `update_frequency` | 5～10 Hz |
| `obstacle_range` | 2.5～4.0 m |
| `raytrace_range` | 3.0～5.0 m，且大于 obstacle_range |
| `inflation_radius` | 0.20～0.35 m |
| `cost_scaling_factor` | 3～8 |
| `transform_tolerance` | 0.2～0.5 s |
| `footprint_padding` | 0.01～0.03 m |

`footprint` 必须来自本车实测外形，包含轮子和突出部件，不可套用其他车型（如四麦克纳姆轮车）的尺寸。初次调参一次只改一类变量并记录：先 TF/里程计，再 footprint/障碍层，再速度加速度，最后轨迹评分。

### 导航验证

- [x] gmapping 建图已完成基本实车演示；雷达无效点修复后，随车移动的大白色圆盘消失（细节与当前参数以实车调试记录为准）
- [x] `slam_toolbox` 曾完成实车建图、保存和重启后加载（历史对照，不是当前建图流程）
- [ ] 保存地图并启动 AMCL 后可稳定定位，推动/遮挡测试可恢复
- [ ] `move_base` 能生成全局和局部路径，原地与窄处不持续振荡
- [ ] 静态和动态障碍物能进入/清除代价地图，无雷达 0 值假障碍
- [x] 多点导航基本实车演示完成；已记录一次约 2 分 42 秒、无碰撞的连续导航（项目路线为 4 个锥筒布置）
- [ ] 测试 ROS 节点退出、数据线拔出、雷达掉线、低电压和重启恢复

---

相关文档：[硬件与接线](hardware.md) · [固件参数配置](firmware.md) · [故障排查](troubleshooting.md) · [ROS 环境搭建](ros-setup.md) · [软件架构](architecture.md)
