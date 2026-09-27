cmake_minimum_required(VERSION 3.0.2)
project(person_follow)

find_package(catkin REQUIRED COMPONENTS
  cv_bridge
  geometry_msgs
  rospy
  sensor_msgs
)

catkin_package()

catkin_install_python(PROGRAMS
  person_detect.py
  person_detect_hog.py
  person_detect_onnx.py
  person_follow.py
  scan_diag.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)

install(DIRECTORY launch/
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}/launch
)
