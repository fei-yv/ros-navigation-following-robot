# YOLOv8n ONNX model

The Release snapshot may include `yolov8n.onnx`, exported from the official Ultralytics `yolov8n.pt` model with:

```bash
pip install ultralytics
yolo export model=yolov8n.pt format=onnx imgsz=320 opset=12
```

Source project: <https://github.com/ultralytics/ultralytics>

The model and the Ultralytics code are distributed under the **AGPL-3.0** license. This notice and the model are separate from the repository's MIT-licensed project code. Keep the AGPL-3.0 terms when using or redistributing the model.
