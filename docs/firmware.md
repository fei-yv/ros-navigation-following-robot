# 固件参数配置（STM32）

本文档面向想复刻本项目的读者，说明拿到轮趣（WheelTEC）官方 STM32 源码后，需要修改哪些文件中的哪些参数，才能适配本车的两轮差速底盘（19:1 减速比、11 线霍尔编码器、0.30m 轮距等）。所有"原始行号"均针对 2025-12-26 版 R550 工程，建立修改副本后行号可能变化，定位时必须同时按"文件 + 函数/变量"查找；ROS 侧的全部修改已整理为本仓库 `patches/` 目录下的补丁，固件侧修改按本文操作。

## 选择正确的源码工程

不同车型（四麦轮、差速、阿克曼 AKM）和不同版本日期的工程不能混用。本车对应的基线工程为：

```text
R550_C30D(2.0)_Mini小车STM32源码_霍尔编码器_2025.12.26
```

对应来源压缩包为 `R550_C30D(2.0)_Mini小车STM32源码_霍尔编码器_2025.12.26.zip`。建议解压后复制一份作为工作目录，原始压缩包和原始工程永久保留，所有修改只做在副本上，便于回退。

注意：

- L150Pro 车型的工程（如 `L150Pro_C30D(2.0)_小车STM32源码_霍尔编码器_2025.11.14`）不能作为本车最终固件。
- V2.0 代码可向下兼容 V1.0，V1.0 不能向上兼容 V2.0；本板为 C30D V2.0，应以 V2.0 工程继续。
- 推荐的目录布局：一个已修改的工作工程 + 一个未修改的原始备份副本目录。Keil 编译和 FlyMcu 烧录只使用工作工程，不要编译备份目录。

## 减速比、编码器、轮径和轮距

### 实际参数入口

文件：

```text
BALANCE\robot_select_init.c
```

原始位置和作用：

| 原始行 | 函数/语句 | 作用 | 本车处理 |
|---:|---|---|---|
| 19 | 读取电位器 ADC 后设置 `Car_Mode` | 决定车型 | 上电确认 OLED 为 `Diff` |
| 24 | `switch(Car_Mode)` | 按车型选择初始化参数 | 使用 `Diff_Car` 分支 |
| 29 | `Robot_Init(Diff_wheelSpacing, 0, 0, HALL_30F, Hall_13, Black_WheelDiameter);` | 差速车默认入口 | 改用本车专用宏 |
| 45 | `Robot_Init(...)` | 参数初始化函数 | 参数最终进入此函数 |
| 58 | `Robot_Parament.GearRatio = GearRatio;` | 减速比 | 目标 19 |
| 61 | `Robot_Parament.EncoderAccuracy = EncoderAccuracy;` | 电机轴编码器线数 | 目标 11 |
| 64 | `Robot_Parament.WheelDiameter = WheelDiameter;` | 轮径 m | 装车承重后实测 |
| 68 | `Encoder_precision = EncoderMultiples * ...` | 输出轴每圈计数 | 预期 `4×11×19=836` |
| 71 | 轮周长计算 | m/圈 | 随有效轮径更新 |
| 74 | `Wheel_spacing` 赋值 | 左右轮距 m | 装车后实测（本车 0.30） |

宏定义文件：

```text
BALANCE\robot_select_init.h
```

| 原始行 | 宏 | 原值 | 本车目标 |
|---:|---|---:|---:|
| 39 | `Diff_wheelSpacing` | `0.16f` | 装车实测值（本车 `0.30f`） |
| 56 | `HALL_30F` | `30` | 新增本车专用减速比宏 `19` |
| 67 | `Hall_13` | `13` | 新增本车专用编码器宏 `11` |
| 88 | `Black_WheelDiameter` | `0.065` | 建议新增差速车专用轮径宏 |
| 101 | `EncoderMultiples` | `4` | 保持 4，除非中断计数验证推翻 |

不要直接把共用的 `Black_WheelDiameter` 改成实测值，因为它还可能被阿克曼和四驱车型引用。推荐新建清晰的本车宏，例如 `DIFF_GEAR_RATIO 19`、`DIFF_ENCODER_LINES 11`、`DIFF_WHEEL_DIAMETER <实测>`，并只在 `Diff_Car` 的 `Robot_Init(...)` 调用中使用。

## 运动模型和车型选择

车型枚举：

```text
BALANCE\system.h
```

- 原始第 47～54 行为车型枚举，`Diff_Car` 的枚举序号为 3。

车型选择和初始化：

```text
BALANCE\robot_select_init.c
```

- 原始第 19 行附近由电位器 ADC 决定 `Car_Mode`，不是编译期永久固定。
- 排障时可暂时强制 `Car_Mode = Diff_Car` 来排除电位器档位问题；正式方案优先保留实体选择功能，并在每次上电确认 OLED 显示 `Diff`。

OLED 显示确认：

```text
BALANCE\show.c
```

- 原始第 162 行和第 436 行包含 `Diff` 显示逻辑。

两轮差速逆运动学：

```text
BALANCE\balance.c
```

- 原始第 223～236 行为差速运动解算。
- 第 226～227 行核心公式：

```c
MOTOR_A.Target = Vx - Vz * Wheel_spacing / 2.0f;
MOTOR_B.Target = Vx + Vz * Wheel_spacing / 2.0f;
```

正运动学和上报速度：

```text
HARDWARE\usartx.c
```

- 原始第 78～82 行为差速车正运动学，第 81 行使用 `Wheel_spacing` 计算角速度。

## 速度限幅和编码器方向

文件：

```text
BALANCE\balance.c
```

- 原始第 108 行 `amplitude = 3.5` 是车轮目标速度限幅。悬空台架可临时降至约 `0.3`，但正式整车的速度/加速度也必须在 ROS `move_base` 层限制。
- 原始第 1036～1062 行包含编码器方向处理和 m/s 换算。若正向命令和反馈符号不一致，应在确认电机动力方向后修正这里对应通道的符号，不可只盲目交换线。
- 实测记录：本车电机线束编码器相位与原厂参考相反（标准接法下前进显示 A-/B-）。已在 Diff 分支（约 1044 行）改为 `Encoder_A_pr=-OriginalEncoder.A; Encoder_B_pr=OriginalEncoder.B`，闭环恢复稳定。该修改需同步应用到自己的工作工程。

## ROS 通信超时停车

文件：

```text
BALANCE\balance.c
```

- 原始第 10 行定义 `u8 command_lost_count`。
- 原始第 295 行附近表明控制循环每 10ms，即 100Hz。
- 原始第 312～314 行的旧逻辑曾被注释，约等于 1 秒。本文所述修改将其恢复/改写为 100Hz 下约 30 次（约 300ms）超时停车，并增加计数器饱和防溢出。

有效控制帧清零位置：

```text
HARDWARE\usartx.c
```

- 原始第 1053 行附近，USART3 收到有效 ROS 控制帧后清零 `command_lost_count`。

官方原版工程中该逻辑处于注释状态，需要恢复或重写。当前实现方式：以 100Hz 控制周期计数约 30 次实现约 300ms 超时，计数器饱和以避免 `u8` 长时间无通信后溢出重新归零。注意：还需在实车上验证——运动中停止 `/cmd_vel` 或拔掉数据连接，检查车轮是否约 300ms 内停下，以及恢复通信后是否不会无命令自行继续。编译和烧录步骤见 [复刻流程 Bringup](bringup.md#阶段-4修改编译和烧录最终固件)。

## USART3 和备用串口

初始化总入口：

```text
BALANCE\system.c
```

- 原始第 141～145 行：USART3 以 115200 初始化，并标注为 ROS 默认口。
- USART1、UART5 也以 115200 初始化，但用途不能混淆。

USART3 具体配置：

```text
HARDWARE\usartx.c
```

- 原始第 404～445 行：PD8/PD9、115200、8N1、无流控。
- 原始第 1006 行起：USART3 接收中断和 ROS 帧解析。

若外部接口不对应预期 USART3，先核对板上丝印、原理图、USB 转串口桥和 PD8/PD9；再按 [故障排查](troubleshooting.md#c30d-的-uart3-接口与预期不符) 选择 USART1/UART5 排障。UART1 还承担烧录，不能在不了解复用关系时直接改作永久 ROS 口。

## Keil 目标芯片

工程文件：

```text
USER\WHEELTEC.uvprojx
```

- 原始第 17 行记录 `STM32F407ZG`。
- 原始第 21 行记录 1MB Flash。
- 原始第 24 行使用 1024KB Flash 算法。

本板实物芯片为 `STM32F407VET6`、512KB。当前状态：已在 Keil GUI 中将 Device 改为 STM32F407VE 并全量编译通过。注意：Flash 下载算法在 DFP 1.0.8 的 Add 列表中未显示 512kB 项，工程文件仍为 `STM32F4xx_1024`，这不影响 FlyMcu 串口烧录，后续若用 Keil 直接下载需补改。

## 烧录工具和当前状态

- 烧录工具：FlyMcu（如 `FlyMcu2188.exe`）。
- USB 串口芯片为 CH9102，安装官方驱动后在 Windows 中枚举出 COM 口（示例中曾为 COM7，端口号随环境可能变化），波特率 115200。
- 当前固件：`OBJ\WHEELTEC.hex`（215618B，MD5 `8D1A9F18CA7769F04F29A70D26175B82`），经 FlyMcu 串口烧录成功。备份目录中的原始工程保留有未修改的原始固件，便于回退。
- 原始工程和其 `OBJ\WHEELTEC.hex` 必须留存，只修改副本。

## Camsense X1 雷达驱动

驱动已包含在本仓库 `src/camsense_driver/`（BSD 3-Clause 许可，已包含雷达无效点 NaN 修复），无需单独获取。以下为源码要点，完整检查步骤见 [复刻流程 Bringup](bringup.md#camsense-x1-的-noetic-兼容检查)，故障备选见 [故障排查](troubleshooting.md#雷达驱动编译或运行失败)。

- 节点为 C++/`roscpp`，不是 Python 节点；Python 2/3 不决定驱动运行，但 Noetic 的 catkin/辅助脚本应使用 Python 3 环境。
- 依赖：`catkin`、`roscpp`、`std_msgs`、`sensor_msgs`、Boost；查看效果还需 RViz。
- 默认 `/dev/ttyUSB0`、115200，发布 `/scan` 和 `/rpms`，`frame_id=laser`，约 400 点/圈，范围约 0.12～8m。
- `launch/view.launch` 默认角度偏移约 16°，必须按实际安装方向验证，不可直接沿用。
- `CMakeLists.txt` 原始安装规则写 `launch rviz`，而实际目录是 `launch` 和 `config`；Noetic 编译/安装前应改为 `launch config`。
- 串口打开失败没有异常捕获，阻塞读取遇到断流可能卡住，当前无自动重连；可临时给 launch 节点加 `respawn="true"`，长期应补异常处理和重连。
- 需验证 `rotationSpeed_` 初始化/除零，以及无效距离写 0 是否会给导航代价地图造成假障碍（本仓库版本已将无效点写为 NaN）。

## 官方源码获取

- STM32 固件工程：从轮趣（WheelTEC）官方渠道（官网资料中心、官方网盘或购买渠道客服）获取对应车型的资料包。本车对应 `R550_C30D(2.0)_Mini小车STM32源码_霍尔编码器_2025.12.26` 工程及 C30D V2.0 控制板资料；官方资料中与本固件相关的文档包括 C30D 随货手册、《单片机与 APP 通信协议》等，是通信协议与说明书的一手来源。
- L150Pro 车型的资料仅用于参考 C30D 板卡资料，不是本车最终车型工程。
- ROS 侧代码：Release 的 `all_code-v1.0.0.zip` 已提供包含本项目修改的 `turn_on_wheeltec_robot`、`wheeltec_robot_rc` 等功能包快照；若从轮趣官方 Noetic 源码重新搭建，再应用本仓库 `patches/` 目录中的补丁。`camsense_driver` 已包含在 `src/camsense_driver/`，无需单独下载。
- 若官方网盘链接失效，应通过轮趣官方渠道重新索取对应车型资料；本仓库不替代原始源码。

## JDY-31 蓝牙适配

USART2 蓝牙控制链路：

```text
轮趣APP → BLE → JDY-31 → USART2(PD5/PD6, 9600) → STM32
```

关键代码位置：

| 文件 | 行 | 内容 |
|---|---|---:|
| `BALANCE\system.c` | 139 | `uart2_init(9600)`（从 115200 改回；JDY-31 出厂默认 9600，原厂备份固件也是 9600） |
| `HARDWARE\usartx.c` | 353-395 | `uart2_init()` 函数：PD5(TX)/PD6(RX)；波特率由调用处决定，本车 **9600**,8N1 |
| `HARDWARE\usartx.c` | 602-702 | `ATCommandFeedBack_BT04A()`：BT04A 连接/断开消息过滤 |
| `HARDWARE\usartx.c` | 706-845 | `ATCommandFeedBack_JDY33()`：JDY-33 连接/断开消息过滤 |
| `HARDWARE\usartx.c` | 802-865 | **`ATCommandFeedBack_JDY31()`**：JDY-31 过滤（本车新增；行号按本车工作工程） |
| `HARDWARE\usartx.c` | 908-912 | USART2 ISR：依次调用 JDY33 → BT04A → JDY31 过滤器 |
| `HARDWARE\usartx.c` | 922 | `41 41` 检测 → 置 `APP_ON_Flag=1`，OLED 显示 "APP" |
| `HARDWARE\usartx.c` | 944 | `Flag_Direction = Usart_Receive - 0x40`（`41`=1=前进） |
| `BALANCE\balance.c` | 333 | `if(APP_ON_Flag) Get_RC()` — APP 模式调用遥控处理 |
| `BALANCE\control.c` | 203-226 | `Get_RC()`：`switch(Flag_Direction)` 设置 `Move_Y` 和 `Angle` |

JDY-31 过滤的消息：

- `OK+CONN\r\n`：BLE 连接成功
- `OK+LOST\r\n`：BLE 断开
- `+START\r\n`：上电启动

---

相关文档：[硬件与接线](hardware.md) · [复刻流程 Bringup](bringup.md) · [ROS 环境搭建](ros-setup.md) · [故障排查](troubleshooting.md) · [软件架构](architecture.md)
