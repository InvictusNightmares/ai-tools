/* Scene behavior: camera-ui. Registered in original execution order. */
var CameraUi = pc.createScript("cameraUi");
CameraUi.attributes.add("buttonImages", {
  array: true,
  type: "entity",
  title: "按钮图片",
});
CameraUi.attributes.add("button_icon_actives", {
  array: true,
  type: "asset",
  assetType: "texture",
  title: "Active图",
});
CameraUi.attributes.add("button_icon_hovers", {
  array: true,
  type: "asset",
  assetType: "texture",
  title: "Normal图",
});
CameraUi.prototype.initialize = function () {
  this.currentCameraIndex = -1;
  this.isActive = false;
  this.controllerCameraHotspotDetail(2);
  this.app.on(
    "phone:hotspot_camera_detail",
    this.controllerCameraHotspotDetail,
    this,
  );
};
CameraUi.prototype.update = function (t) {};
CameraUi.prototype.controllerCameraHotspotDetail = function (t) {
  for (var e = 0; e < this.buttonImages.length; e++)
    e === t
      ? ((this.isActive = true),
        (this.buttonImages[e].element.textureAsset =
          this.button_icon_actives[e]),
        window.parent &&
          window.parent.funcHotB &&
          window.parent.funcHotB(true, t + 1))
      : (this.buttonImages[e].element.textureAsset =
          this.button_icon_hovers[e]);
};
