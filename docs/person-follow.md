# 人员跟随

本文说明人员跟随子系统的原理、代码结构和运行方法。代码位于 [`src/person_follow/`](../src/person_follow/)，现在是一个可以直接放进 catkin 工作空间编译的 ROS 包。不依赖建图导航栈——即使不做建图导航，只启动底盘、雷达和摄像头也可以运行跟随功能。

## 系统结构

```text
usb_cam (/usb_cam/image_raw)
   └─> person_detect_onnx.py    YOLOv8n ONNX 推理，只检测 person 类
         └─> /person/bbox       (sensor_msgs/RegionOfInterest，置信度最高的一个人)
               └─> person_follow.py    P 控制 + 死区 + 低通 + 避障
                     └─> /cmd_vel  → 底盘
/scan ───────────────────────────┘ 前方锥形区域障碍：减速 / 急停
```

要点：

- 检测和跟随分成两个节点，`/person/bbox` 用标准的 `RegionOfInterest` 消息传递，方便单独替换检测器（仓库里附带了 HOG 版 `person_detect_hog.py` 和 PyTorch 版 `person_detect.py` 作为对照实现）。
- 跟随节点直接发 `/cmd_vel`，与键盘遥控、导航共用同一控制口。**运行跟随前确认没有其他节点（键盘遥控 / move_base）同时在发 `/cmd_vel`**。
- `scan_diag.py` 是一个雷达诊断小工具，用于查看 `/scan` 前方区域的距离读数。

## 检测节点 person_detect_onnx.py

用 onnxruntime 在 CPU 上运行 YOLOv8 导出的 ONNX 模型，letterbox 预处理 + NMS，把置信度最高的人的检测框发布到 `/person/bbox`。

**为什么用 ONNX 而不是直接跑 YOLOv8：** 小主机 CPU 不支持 AVX/AVX2 指令集，安装 PyTorch/Ultralytics 后在 import 或推理时会触发非法指令崩溃。ONNX Runtime 的 CPU 版没有这个限制，整机单机即可运行。

参数（均可用 `_key:=value` 覆盖）：

| 参数 | 默认值 | 说明 |
|---|---|---|
| `~model` | `/home/robot/catkin_ws/src/person_follow/models/yolov8n.onnx` | ONNX 模型路径，建议显式指定 |
| `~conf` | 0.5 | 置信度阈值 |
| `~imgsz` | 320 | 模型输入边长，须与导出时一致 |
| `~iou` | 0.45 | NMS IoU 阈值 |
| `~publish_debug` | true | 发布带框调试图到 `/person/debug/compressed`（可用 `rqt_image_view` 查看） |

## 模型导出

在有一块正常显卡或较新 CPU、可安装完整 Python 环境的电脑上执行：

```bash
pip install ultralytics
yolo export model=yolov8n.pt format=onnx imgsz=320 opset=12
```

得到约 13 MB 的 `yolov8n.onnx`，放到 `src/person_follow/models/`（Release 快照中已放好）即可。

> 许可说明：这里的 `yolov8n.onnx` 由 Ultralytics 官方发布的 `yolov8n.pt` 导出，模型及相关代码遵循 AGPL-3.0，与本仓库的 MIT 代码分开。Release 快照包含该 ONNX 文件；使用或再分发时请同时遵守 AGPL-3.0。模型来源和导出信息记录在 Release 内 `person_follow/models/README.md`。

## 跟随节点 person_follow.py

10 Hz 控制周期，每周期按下面的顺序计算 `/cmd_vel`：

1. **角速度**：目标框中心相对画面中心的水平像素偏差 × `k_angular`(0.0015)，`angular_deadzone`(60 px) 死区内不转，防止左右摆头。
2. **线速度**：单目测距 `depth = K_depth / 框高像素`，与目标距离 `target_depth`(2.0 m) 之差 × `k_linear`(0.3)，`linear_deadzone`(0.2 m) 死区内不进不退。
3. **限幅**：线速度 ±0.3 m/s，角速度 ±0.25 rad/s。
4. **低通滤波**：`alpha`(0.3) 一阶低通平滑输出，抑制打滑和检测抖动引起的突变。
5. **转向降速**：转向越猛线速度按比例降得越多（`turn_slowdown`=0.8），减少差速底盘侧滑。
6. **丢失搜索**：丢目标超过 `lost_timeout`(1 s) 后，原地以 `search_angular`(0.3 rad/s) 慢速转圈直到重新框到人。
7. **避障（最高优先级）**：取 `/scan` 前方 ±`front_angle`(30°) 锥形内最近障碍：小于 `stop_dist`(0.30 m) 停车，小于 `slow_dist`(0.60 m) 线性减速；只约束前进，不影响转向和后退。

完整参数列表（均可用 `_key:=value` 覆盖）：

| 参数 | 默认值 | 说明 |
|---|---|---|
| `~img_width` | 640 | 画面宽度像素，须与 usb_cam 分辨率一致 |
| `~k_angular` | 0.0015 | 角速度增益，越小越不摆头但转向越慢 |
| `~k_linear` | 0.3 | 线速度增益 |
| `~target_depth` | 2.0 | 目标跟随距离（m） |
| `~K_depth` | 900 | 单目估距系数 = 焦距(px) × 人身高(m)，需实测标定 |
| `~max_angular` | 0.25 | 角速度限幅（rad/s） |
| `~max_linear` | 0.3 | 线速度限幅（m/s） |
| `~alpha` | 0.3 | 低通滤波系数（0~1，越小越平滑） |
| `~turn_slowdown` | 0.8 | 转向降速强度 |
| `~lost_timeout` | 1.0 | 丢目标进入搜索的等待时间（s） |
| `~angular_deadzone` | 60 | 角速度死区（px） |
| `~linear_deadzone` | 0.2 | 线速度死区（m） |
| `~search_angular` | 0.3 | 丢失后原地转圈的角速度（rad/s） |
| `~search_direction` | +1 | 搜索转向方向（+1 左 / -1 右） |
| `~stop_dist` | 0.30 | 前方障碍急停距离（m） |
| `~slow_dist` | 0.60 | 前方障碍开始减速的距离（m） |
| `~front_angle` | 30 | 前方锥形避障半角（度） |

## 运行步骤（小主机端）

前置：底盘与雷达的启动方式与建图阶段相同（见 [复刻流程](bringup.md)），另需安装 `ros-noetic-usb-cam`。

把 `src/person_follow/` 放入 `~/catkin_ws/src/` 后，先安装 ROS 依赖并编译：

```bash
cd ~/catkin_ws
rosdep install --from-paths src --ignore-src -r -y
catkin_make
source devel/setup.bash
```

ONNX 版本还需要在小主机上安装 `onnxruntime`、`opencv-python`、`numpy`，并确保
`cv_bridge` 可用。Release 快照中的模型位于 `person_follow/models/yolov8n.onnx`；从 Git 仓库源码重新搭建时，可按上面的命令导出并放入同一目录。

```bash
# 1. 启动底盘 + 雷达（同建图阶段的启动方式，不要启动 gmapping）

# 2. 启动摄像头
rosrun usb_cam usb_cam_node _video_device:=/dev/video0 _image_width:=640 _image_height:=480

# 3. 启动检测节点和跟随节点（推荐）
roslaunch person_follow person_follow_onnx.launch \
  model:=/home/robot/catkin_ws/src/person_follow/models/yolov8n.onnx \
  conf:=0.5 target_depth:=2.0

# 没有 ONNX 模型时，先用 OpenCV HOG 验证控制链路
roslaunch person_follow person_follow_hog.launch
```

调试时可另开终端 `rqt_image_view` 订阅 `/person/debug/compressed` 查看检测框；用 `scan_diag.py` 核对雷达前方读数是否与实际障碍一致。

## K_depth 标定

`K_depth ≈ 焦距(像素) × 目标身高(m)`，出厂默认 900 只是参考值。标定方法：让人站在已知距离 `d`（如 2 m）处，读出检测框高度 `h_px`，则 `K_depth = d × h_px`。换用不同分辨率后需要重新标定。

## 调参与已知问题

- 检测稳定性受光照、遮挡影响明显；多人同框时跟随置信度最高的一个。
- 控制频率受 CPU 占用和摄像头帧率限制；usb_cam 分辨率改变时要同步改 `~img_width`。
- 目标下蹲、转身等导致框高突变的动作会引起距离估计波动，可减小 `~alpha` 平滑（牺牲响应速度）。
