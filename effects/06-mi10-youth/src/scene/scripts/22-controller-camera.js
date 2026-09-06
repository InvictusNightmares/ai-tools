/* Scene behavior: controller-camera. Registered in original execution order. */
var ControllerCamera = pc.createScript("controllerCamera");
ControllerCamera.attributes.add("blastCameraDistanceCurve", {
  type: "curve",
  title: "动画过度曲线",
});
ControllerCamera.attributes.add("blastCameraFovCurve", {
  type: "curve",
  title: "FOV过度曲线",
});
ControllerCamera.attributes.add("beginCameraRotateCurve", {
  type: "curve",
  title: "开始相机旋转曲线",
});
ControllerCamera.attributes.add("boxCameraDistanceMax", {
  type: "number",
  default: 6,
  title: "旋转1后cam最远距离",
});
ControllerCamera.attributes.add("boxCameraDistanceMin", {
  type: "number",
  default: 4,
  title: "旋转1后cam最近距离",
});
ControllerCamera.attributes.add("beginRotateCamToPitch", {
  type: "number",
  default: -30,
  title: "旋转1后cam的最终pitch",
});
ControllerCamera.attributes.add("beginCameraDistanceMax", {
  type: "number",
  default: 4,
  title: "交互开始后cam最远距离",
});
ControllerCamera.attributes.add("beginCameraDistanceMin", {
  type: "number",
  default: 2.5,
  title: "交互开始后cam最近距离",
});
ControllerCamera.attributes.add("blastResetCameraPitch", {
  type: "number",
  default: -15,
  title: "炸开时的cam的Pitch",
});
ControllerCamera.attributes.add("blastResetCameraYaw", {
  type: "number",
  default: -45,
  title: "炸开时的cam的Yaw",
});
ControllerCamera.attributes.add("blastCameraFov", {
  type: "number",
  default: 8,
  title: "炸开时cam FOV",
});
ControllerCamera.attributes.add("blastCameraDistanceMax", {
  type: "number",
  default: 15,
  title: "炸开时cam最远距离",
});
ControllerCamera.attributes.add("blastCameraDistanceMin", {
  type: "number",
  default: 10,
  title: "炸开时cam最近距离",
});
ControllerCamera.attributes.add("goToCameraResetCameraPitch", {
  type: "number",
  default: 0,
  title: "看相机时cam的Pitch",
});
ControllerCamera.attributes.add("goToCameraResetCameraYaw", {
  type: "number",
  default: 90,
  title: "看相机时cam的Yaw",
});
ControllerCamera.attributes.add("goToCameraCameraFov", {
  type: "number",
  default: 10,
  title: "看相机时cam FOV",
});
ControllerCamera.attributes.add("goToCameraCameraDistanceMax", {
  type: "number",
  default: 6,
  title: "看相机时cam最远距离",
});
ControllerCamera.attributes.add("goToCameraCameraDistanceMin", {
  type: "number",
  default: 6,
  title: "看相机时cam最近距离",
});
ControllerCamera.attributes.add("camMDResetCameraYaw_0", {
  type: "number",
  default: 180,
  title: "进入相机时cam的Yaw",
});
ControllerCamera.attributes.add("camMDResetCameraYaw_1", {
  type: "number",
  default: 0,
  title: "出来相机时cam的Yaw",
});
ControllerCamera.attributes.add("camMDResetCameraPitch_0", {
  type: "number",
  default: 60,
  title: "进入相机时cam的Pitch",
});
ControllerCamera.attributes.add("camMDResetCameraPitch_1", {
  type: "number",
  default: 0,
  title: "出来相机时cam的Pitch",
});
ControllerCamera.attributes.add("camMDResetCameraYaw_2", {
  type: "number",
  default: -90,
  title: "在相机内cam的Yaw",
});
ControllerCamera.attributes.add("camMDResetCameraPitch_2", {
  type: "number",
  default: 45,
  title: "在相机内cam的Pitch",
});
ControllerCamera.attributes.add("camMDCameraDistanceMax", {
  type: "number",
  default: 2,
  title: "进相机时cam最远距离",
});
ControllerCamera.attributes.add("camMDCameraDistanceMin", {
  type: "number",
  default: 0,
  title: "进相机时cam最近距离",
});
ControllerCamera.attributes.add("leaveMDCameraDistanceMax", {
  type: "number",
  default: 1.5,
  title: "出相机时cam最远距离",
});
ControllerCamera.attributes.add("leaveMDCameraDistanceMin", {
  type: "number",
  default: 1.5,
  title: "出相机时cam最近距离",
});
ControllerCamera.attributes.add("boxButton", {
  type: "entity",
  title: "测试UI_1",
});
ControllerCamera.attributes.add("UIGround", {
  type: "entity",
  title: "测试UI_2",
});
ControllerCamera.attributes.add("boxs", {
  type: "entity",
  array: true,
  title: "手机盒子",
});
ControllerCamera.attributes.add("phone", {
  type: "entity",
  title: "手机",
});
ControllerCamera.attributes.add("phoneRotateAngles", {
  type: "vec3",
  title: "开箱手机翻转角度",
});
ControllerCamera.attributes.add("isTestRotate", {
  type: "boolean",
});
var toogleCameraRotate = true;
var toogleCameraPitch = true;
ControllerCamera.prototype.initialize = function () {
  this.orbitCamera = this.entity.script.orbitCamera;
  this.orbitCamera.yaw = 0;
  this.orbitCamera.pitchAngleMax = 80;
  this.orbitCamera.pitchAngleMin = 20;
  toogleCameraRotate = false;
  var t = this;
  this.orbitCamera.pivotPoint.add(this.phone.getLocalPosition().clone());
  this.currentPhoneState = 0;
  this.isBlast = false;
  this.isGoToCamera = false;
  this.is50x = false;
  this.formYaw = this.orbitCamera.yaw;
  this.toYaw = this.orbitCamera.yaw + 180;
  this.fromPitch = this.orbitCamera.pitch;
  this.toPitch = this.beginRotateCamToPitch;
  this.isBeginRotate = false;
  this.isOpenBox = false;
  this.isPanCamera = false;
  this.animTimeCount = 0;
  this.animDuration = 1;
  this.fromUpZ = this.boxs[0].getLocalPosition().z;
  this.toUpZ = -1 + this.fromUpZ;
  this.fromPhoneAngles = this.phone.getLocalEulerAngles().clone();
  this.toPhoneAngles = this.phoneRotateAngles.clone();
  this.fromPhonePosition = this.phone.getLocalPosition().clone();
  this.toPhonePosition = new pc.Vec3();
  this.camPanPivotPointZero = new pc.Vec3();
  this.fromCamPivotPoint = this.orbitCamera.pivotPoint.clone();
  this.toCamPivotPoint = new pc.Vec3();
  this.isGoInPhone = false;
  this.isPlayingState3 = false;
  this.UIGround.enabled = false;
  this.boxButton.enabled = false;
  this.app.on("cam_beginRotate", function () {
    t.app.fire("background_fade", 0);
    t.isBeginRotate = true;
  });
  this.app.on("cam_openBox", function () {
    t.orbitCamera.pitchAngleMax = 80;
    t.orbitCamera.pitchAngleMin = -80;
    t.orbitCamera.yaw = 180;
    t.orbitCamera.pitch = t.beginRotateCamToPitch;
    toogleCameraRotate = false;
    t.boxButton.enabled = false;
    t.isOpenBox = true;
    t.app.fire("box:fadeOutEye");
  });
  this.beginBlastCamFov = this.entity.camera.fov;
  this.endBlastCamFov = this.blastCameraFov;
  this.beginGoToCamCamFov = this.entity.camera.fov;
  this.endGoToCamCamFov = this.goToCameraCameraFov;
  this.fromCamFov = this.beginBlastCamFov;
  this.toCamFov = this.blastCameraFov;
  this.currentCamFov = this.beginBlastCamFov;
  this.beginBlastDistanceMax = this.beginCameraDistanceMax;
  this.endBlastDistanceMax = this.blastCameraDistanceMax;
  this.beginBlastDistanceMin = this.beginCameraDistanceMin;
  this.endBlastDistanceMin = this.blastCameraDistanceMin;
  this.beginGoToCamDistanceMax = this.beginCameraDistanceMax;
  this.endGoToCamDistanceMax = this.goToCameraCameraDistanceMax;
  this.beginGoToCamDistanceMin = this.beginCameraDistanceMin;
  this.endGoToCamDistanceMin = this.goToCameraCameraDistanceMin;
  this.fromDistanceMax = this.orbitCamera.distanceMax;
  this.toDistanceMax = this.boxCameraDistanceMax;
  this.currentDistanceMax = this.beginCameraDistanceMax;
  this.fromDistanceMin = this.orbitCamera.distanceMin;
  this.toDistanceMin = this.boxCameraDistanceMin;
  this.currentDistanceMin = this.beginCameraDistanceMin;
  this.app.on("cam_controllerCameraParam", function (a, e) {
    switch (
      ((t.currentPhoneState = e),
      (toogleCameraRotate = false),
      (toogleCameraPitch = !a),
      (t.animTimeCount = 0),
      (t.fromCamFov = t.currentCamFov),
      (t.fromDistanceMax = t.currentDistanceMax),
      (t.fromDistanceMin = t.currentDistanceMin),
      (t.formYaw = t.orbitCamera.yaw),
      (t.fromPitch = t.orbitCamera.pitch),
      (t.fromCamPivotPoint = t.orbitCamera.pivotPoint.clone()),
      (t.orbitCamera.inertiaFactor = 0.1),
      e)
    ) {
      case 0:
        break;
      case 1:
        t.isBlast = a;
        t.isGoToCamera = false;
        t.is50x = false;
        a
          ? ((t.toCamFov = t.endBlastCamFov),
            (t.toDistanceMax = t.endBlastDistanceMax),
            (t.toDistanceMin = t.endBlastDistanceMin),
            (t.orbitCamera.pitch = t.blastResetCameraPitch),
            (t.orbitCamera.yaw = t.blastResetCameraYaw))
          : ((t.toCamFov = t.beginBlastCamFov),
            (t.toDistanceMax = t.beginBlastDistanceMax),
            (t.toDistanceMin = t.beginBlastDistanceMin),
            (t.orbitCamera.pitch = 0),
            (t.orbitCamera.yaw = 0));
        break;
      case 2:
        t.isBlast = false;
        t.isGoToCamera = a;
        t.is50x = false;
        a
          ? ((t.toCamFov = t.endGoToCamCamFov),
            (t.toDistanceMax = t.endGoToCamDistanceMax),
            (t.toDistanceMin = t.endGoToCamDistanceMin),
            (t.orbitCamera.pitch = t.goToCameraResetCameraPitch),
            (t.orbitCamera.yaw = t.goToCameraResetCameraYaw))
          : ((t.toCamFov = t.beginGoToCamCamFov),
            (t.toDistanceMax = t.beginGoToCamDistanceMax),
            (t.toDistanceMin = t.beginGoToCamDistanceMin),
            (t.orbitCamera.pitch = 0),
            (t.orbitCamera.yaw = 0));
        break;
      case 3:
        t.isBlast = false;
        t.isGoToCamera = false;
        t.is50x = a;
        t.toCamFov = t.beginGoToCamCamFov;
        t.isPlayingState3 = a;
        t.orbitCamera.inertiaFactor = 0.2;
        a
          ? t.isGoInPhone
            ? ((t.toDistanceMax = t.leaveMDCameraDistanceMax),
              (t.toDistanceMin = t.leaveMDCameraDistanceMin),
              (t.orbitCamera.yaw = t.camMDResetCameraYaw_1),
              (t.orbitCamera.pitch = t.camMDResetCameraPitch_1),
              (t.isGoInPhone = false))
            : ((t.toDistanceMax = t.camMDCameraDistanceMax),
              (t.toDistanceMin = t.camMDCameraDistanceMin),
              (t.orbitCamera.yaw = t.camMDResetCameraYaw_0),
              (t.orbitCamera.pitch = t.camMDResetCameraPitch_1),
              (t.isGoInPhone = true))
          : ((t.toCamPivotPoint = t.camPanPivotPointZero),
            (t.toDistanceMax = t.beginCameraDistanceMax),
            (t.toDistanceMin = t.beginCameraDistanceMin),
            (t.orbitCamera.yaw = 0),
            (t.orbitCamera.pitch = 0),
            (t.isGoInPhone = false));
    }
    t.isStopAnim = true;
  });
  this.app.on("cam_outSetCameraPan", function () {
    t.orbitCamera.yaw = t.camMDResetCameraYaw_2;
    t.orbitCamera.pitch = t.camMDResetCameraPitch_2;
  });
  this.global_ui = null;
  this.isTestRotate && this.app.fire("cam_beginRotate");
};
ControllerCamera.prototype.update = function (t) {
  if (0 === this.currentPhoneState) {
    if (
      this.isBeginRotate &&
      false === this.isOpenBox &&
      false === this.isPanCamera
    ) {
      if (0.3 * this.animTimeCount > 1) {
        this.global_ui && (this.global_ui.style.pointerEvents = "auto");
        toogleCameraRotate = true;
        this.boxButton.enabled = true;
        this.fromDistanceMax = this.orbitCamera.distanceMax;
        this.fromDistanceMin = this.orbitCamera.distanceMin;
        this.toDistanceMax = this.beginCameraDistanceMax;
        this.toDistanceMin = this.beginCameraDistanceMin;
        this.animTimeCount = 0;
        this.isBeginRotate = false;
      } else {
        this.animTimeCount += t;
        var a,
          e = pc.math.clamp(
            (0.3 * this.animTimeCount) / this.animDuration,
            0,
            1,
          );
        a = pc.math.lerp(
          this.formYaw,
          this.toYaw,
          this.beginCameraRotateCurve.value(e),
        );
        this.orbitCamera.yaw = a;
        var i;
        i = pc.math.lerp(
          this.fromPitch,
          this.toPitch,
          this.beginCameraRotateCurve.value(e),
        );
        this.orbitCamera.pitch = i;
        var o, r;
        o = pc.math.lerp(
          this.fromDistanceMax,
          this.toDistanceMax,
          this.beginCameraRotateCurve.value(e),
        );
        r = pc.math.lerp(
          this.fromDistanceMin,
          this.toDistanceMin,
          this.beginCameraRotateCurve.value(e),
        );
        this.orbitCamera.distanceMax = o;
        this.orbitCamera.distanceMin = r;
        this.orbitCamera.distance =
          (this.orbitCamera.distanceMax + this.orbitCamera.distanceMin) / 2;
      }
    }
    if (
      this.isOpenBox &&
      false === this.isBeginRotate &&
      false === this.isPanCamera
    ) {
      if (0.65 * this.animTimeCount > 1) {
        this.boxs[0].enabled = false;
        this.fromPitch = this.orbitCamera.pitch;
        this.toPitch = 0;
        this.app.fire("phone:resetPosition", this.toPhonePosition, 1.5, 0);
        this.app.fire("phone:resetRotation", this.toPhoneAngles, 1.5, 0);
        this.isPanCamera = true;
        this.animTimeCount = 0;
        this.isOpenBox = false;
      } else {
        this.animTimeCount += t;
        var s = pc.math.clamp(
          (0.65 * this.animTimeCount) / this.animDuration,
          0,
          1,
        );
        this.boxs[0].model.meshInstances[0].material.opacity = 1 - s;
        this.boxs[0].model.meshInstances[0].material.update();
        var n;
        n = pc.math.lerp(
          this.fromUpZ,
          this.toUpZ,
          this.beginCameraRotateCurve.value(s),
        );
        this.boxs[0].setLocalPosition(0, 0, n);
      }
    }
    if (
      this.isPanCamera &&
      false === this.isOpenBox &&
      false === this.isBeginRotate
    ) {
      if (0.65 * this.animTimeCount > 1) {
        this.boxs[1].enabled = false;
        this.boxs[2].enabled = false;
        this.app.fire("assetManager:unload_unboxing_textures");
        toogleCameraRotate = true;
        this.UIGround.enabled = true;
        this.animTimeCount = 0;
        this.isPanCamera = false;
      } else {
        this.animTimeCount += t;
        var m,
          C = pc.math.clamp(
            (0.65 * this.animTimeCount) / this.animDuration,
            0,
            1,
          );
        m = pc.math.lerpAngle(
          this.fromPitch,
          this.toPitch,
          this.beginCameraRotateCurve.value(C),
        );
        this.orbitCamera.pitch = m;
        var h = new pc.Vec3(0, 0, 0);
        h.x = pc.math.lerp(
          this.fromCamPivotPoint.x,
          this.toCamPivotPoint.x,
          this.beginCameraRotateCurve.value(C),
        );
        h.y = pc.math.lerp(
          this.fromCamPivotPoint.y,
          this.toCamPivotPoint.y,
          this.beginCameraRotateCurve.value(C),
        );
        h.z = pc.math.lerp(
          this.fromCamPivotPoint.z,
          this.toCamPivotPoint.z,
          this.beginCameraRotateCurve.value(C),
        );
        this.orbitCamera.pivotPoint.set(h.x, h.y, h.z);
        var c, l;
        c = pc.math.lerp(
          this.fromDistanceMax,
          this.toDistanceMax,
          this.beginCameraRotateCurve.value(C),
        );
        l = pc.math.lerp(
          this.fromDistanceMin,
          this.toDistanceMin,
          this.beginCameraRotateCurve.value(C),
        );
        this.orbitCamera.distanceMax = c;
        this.orbitCamera.distanceMin = l;
        this.orbitCamera.distance =
          (this.orbitCamera.distanceMax + this.orbitCamera.distanceMin) / 2;
      }
    }
  } else if (this.animTimeCount <= 1) {
    3 != this.currentPhoneState
      ? (this.animTimeCount += t)
      : this.isPlayingState3
        ? this.isGoInPhone
          ? (this.animTimeCount += t / 3)
          : (this.animTimeCount += t / 1.5)
        : (this.animTimeCount += t);
    var b;
    b = pc.math.lerp(
      this.fromCamFov,
      this.toCamFov,
      this.blastCameraFovCurve.value(this.animTimeCount / this.animDuration),
    );
    this.entity.camera.fov = b;
    this.currentCamFov = b;
    var u, p;
    u = pc.math.lerp(
      this.fromDistanceMax,
      this.toDistanceMax,
      this.blastCameraDistanceCurve.value(
        this.animTimeCount / this.animDuration,
      ),
    );
    p = pc.math.lerp(
      this.fromDistanceMin,
      this.toDistanceMin,
      this.blastCameraDistanceCurve.value(
        this.animTimeCount / this.animDuration,
      ),
    );
    this.orbitCamera.distanceMax = u;
    this.orbitCamera.distanceMin = p;
    this.orbitCamera.distance =
      (this.orbitCamera.distanceMax + this.orbitCamera.distanceMin) / 2;
    this.currentDistanceMax = u;
    this.currentDistanceMin = p;
  } else if (this.isStopAnim) {
    switch (this.currentPhoneState) {
      case 1:
        toogleCameraRotate = true;
        break;
      case 2:
        false === this.isGoToCamera && (toogleCameraRotate = true);
        break;
      case 3:
        false === this.is50x && (toogleCameraRotate = true);
    }
    this.isStopAnim = false;
  }
};
