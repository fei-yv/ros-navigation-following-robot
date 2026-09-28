# 地图与航点

本目录保存项目实测得到的 ROS 栅格地图和多点导航航点文件，仅用于展示项目结果、理解文件格式和复现实验记录。

> **重要：这些文件不是通用地图或通用航点配置，不能直接用于其他场地或其他小车。** 使用自己的场地时，必须重新建图、保存地图、设置 AMCL 初始位姿，并在同一张地图上重新采集航点。

| 文件 | 说明 |
|---|---|
| `last2.yaml` + `last2.pgm` | 地图版本 2，仅包含地图文件 |
| `last6.yaml` + `last6.pgm` | 地图版本 6，与 `last6.xml` 配套使用 |
| `last6.xml` | `waterplus_map_tools` 航点文件，共 16 个航点 |

YAML 使用相对图片路径，因此整组文件可以直接复制到同一目录。它们只适合复现本项目记录的场地；启动导航前仍需确认地图、底盘坐标系、雷达安装位置和小车实际环境一致。使用多点导航时，地图和 `last6.xml` 必须来自同一套坐标系。

以下命令仅用于查看本项目示例文件的调用方式，不代表换到其他场地后可以直接运行：

```bash
roslaunch turn_on_wheeltec_robot navigation.launch \
  map_file:=/path/to/ros-navigation-following-robot/maps/last6.yaml

rosrun waterplus_map_tools wp_manager \
  _load:=/path/to/ros-navigation-following-robot/maps/last6.xml
```
