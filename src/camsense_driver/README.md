# Camsense X1 ROS 驱动

这是一个 ROS Noetic 可用的 Camsense X1 驱动包，节点名为
`camsense_publisher`，发布 `/scan` 和 `/rpms`。原始驱动遵循 BSD 3-Clause
许可；本仓库额外保留了质量值为 0 的回波为 `NaN`，避免 SLAM 把无效数据误判成
车身附近的障碍物。

## 编译

将本目录放入 catkin 工作空间的 `src/` 后执行：

```bash
cd ~/catkin_ws
catkin_make
source devel/setup.bash
```

## 运行

```bash
rosrun camsense_driver camsense_publisher \
  _port:=/dev/camsense_x1 _frame_id:=laser _offset:=16.0
```

`port`、`frame_id`、`baud_rate` 和 `offset` 都是私有参数。实际安装后应先用
`rostopic echo /scan` 检查数据，再通过 TF 和实物核对 0° 是否指向车头。
