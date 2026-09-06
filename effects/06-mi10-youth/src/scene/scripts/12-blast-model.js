/* Scene behavior: blast-model. Registered in original execution order. */
var BlastModel = pc.createScript("blastModel");
BlastModel.attributes.add("phone", {
  type: "entity",
  title: "手机",
});
BlastModel.attributes.add("phoneCamera", {
  type: "entity",
  title: "手机相机",
});
BlastModel.attributes.add("animCurve", {
  type: "curve",
  title: "炸开过度曲线",
});
BlastModel.attributes.add("blastModes", {
  type: "entity",
  array: true,
  title: "需要炸开的模型",
});
BlastModel.attributes.add("blastModelPositionEntity", {
  type: "entity",
  array: true,
  title: "炸开位置点Entity",
});
BlastModel.attributes.add("blastPhoneRotate", {
  type: "vec3",
  title: "炸开时手机角度",
});
BlastModel.attributes.add("blastPhoneCamRotate", {
  type: "vec3",
  title: "炸开时相机零件角度",
});
BlastModel.attributes.add("goToCameraPhoneRotate", {
  type: "vec3",
  title: "观看相机时手机角度",
});
BlastModel.attributes.add("goToCameraPosition", {
  type: "vec3",
  title: "观看相机时手机平移位置",
});
BlastModel.attributes.add("fivetyCameraPosition", {
  type: "vec3",
  title: "50x相机时手机平移位置",
});
BlastModel.attributes.add("cameraHotspot", {
  type: "entity",
  title: "相机UI",
});
BlastModel.attributes.add("hotspotBlastEntitys", {
  type: "entity",
  array: true,
  title: "炸开热点",
});
BlastModel.attributes.add("hotspotBlastDetails", {
  type: "entity",
  array: true,
  title: "炸开热点详情",
});
BlastModel.attributes.add("hotspotBlastOtherOne", {
  type: "entity",
  title: "多一个炸开热点",
});
BlastModel.attributes.add("hotspotBlastOtherOneDetail", {
  type: "entity",
  title: "多一个炸开热点详情",
});
BlastModel.attributes.add("whiteBG", {
  type: "asset",
  assetType: "material",
  title: "白背景球",
});
BlastModel.attributes.add("cam1", {
  type: "entity",
  title: "相机1",
});
BlastModel.attributes.add("cam2", {
  type: "entity",
  title: "相机2",
});
BlastModel.attributes.add("multipleModels", {
  type: "entity",
  array: true,
  title: "50倍变焦",
});
BlastModel.attributes.add("cam2Position_0", {
  type: "vec3",
  title: "相机2第一段位置",
});
BlastModel.prototype.initialize = function () {
  this.currentState = 0;
  var t = this;
  if (
    ((this.beginPhoneAngle = new pc.Vec3()),
    (this.beginPhoneCamAngle = this.phoneCamera.getLocalEulerAngles().clone()),
    (this.beginPhonePosition = new pc.Vec3()),
    (this.beginPositions = []),
    (this.endPositions = []),
    (this.currentPositions = []),
    (this.fromPositions = []),
    (this.toPositions = []),
    this.blastModes.length > 0 && this.blastModelPositionEntity.length > 0)
  )
    for (var e = 0; e < this.blastModes.length; e++) {
      this.beginPositions[e] = this.blastModes[e].getLocalPosition().clone();
      this.endPositions[e] = this.blastModelPositionEntity[e]
        .getLocalPosition()
        .clone();
      this.currentPositions[e] = this.blastModes[e].getLocalPosition().clone();
      this.fromPositions[e] = this.blastModes[e].getLocalPosition().clone();
      this.toPositions[e] = this.blastModelPositionEntity[e]
        .getLocalPosition()
        .clone();
    }
  if (
    ((this.cameraHotspot.enabled = false),
    (this.animTimeCount = 1),
    (this.animDuration = 1),
    (this.isBlast = false),
    (this.isGoToCamera = false),
    (this.is50x = false),
    this.cam2 &&
      ((this.cam2BeginPosition = this.cam2.getLocalPosition().clone()),
      (this.cam2BeginAngles = this.cam2.getLocalEulerAngles().clone()),
      (this.currentCam2Position = this.cam2.getLocalPosition().clone()),
      (this.currentCam2Angles = this.cam2.getLocalEulerAngles().clone())),
    (this.isEnd50XAnim = false),
    this.multipleModels.length)
  )
    for (var i = 0; i < this.multipleModels.length; i++)
      this.multipleModels[i].enabled = false;
  for (var s = 0; s < this.hotspotBlastEntitys.length; s++)
    this.hotspotBlastEntitys[s].enabled = false;
  this.currentBlastHotIndex = -1;
  for (var o = 0; o < this.hotspotBlastDetails.length; o++)
    this.hotspotBlastDetails[o].enabled = false;
  this.hotspotBlastOtherOne &&
    this.hotspotBlastOtherOneDetail &&
    ((this.hotspotBlastOtherOne.enabled = false),
    (this.hotspotBlastOtherOneDetail.enabled = false));
  this.app.on(
    "phone:hotspot_blast_detail",
    this.controllerBlastHotspotDetail,
    this,
  );
  this.app.on("phone:anim_controller", this.controllerAnim, this);
  this.app.on("phone:resetPosition", this.resetPosition, this);
  this.app.on("phone:resetRotation", this.resetRotation, this);
  this.preColorIndex = 0;
  this.currentColorIndex = 0;
  this.app.on("save:currentColorIndex", function (e) {
    t.currentColorIndex = e;
  });
  this.whiteBGFadeActivated = false;
  this.whiteBGFadeIn = true;
};
BlastModel.prototype.update = function (t) {
  if (this.animTimeCount >= 1) {
    if (this.isStopAnim) {
      switch (this.currentState) {
        case 1:
          if (true === this.isBlast) {
            for (var e = 0; e < this.hotspotBlastEntitys.length; e++)
              this.hotspotBlastEntitys[e].enabled = this.isBlast;
            this.hotspotBlastOtherOne.enabled = this.isBlast;
          }
          break;
        case 2:
          false === this.isGoToCamera || (this.cameraHotspot.enabled = 1);
      }
      this.isStopAnim = false;
    }
  } else {
    for (this.animTimeCount += t, i = 0; i < this.blastModes.length; i++) {
      var s = new pc.Vec3(0, 0, 0);
      s.x = pc.math.lerp(
        this.fromPositions[i].x,
        this.toPositions[i].x,
        this.animCurve.value(this.animTimeCount / this.animDuration),
      );
      s.y = pc.math.lerp(
        this.fromPositions[i].y,
        this.toPositions[i].y,
        this.animCurve.value(this.animTimeCount / this.animDuration),
      );
      s.z = pc.math.lerp(
        this.fromPositions[i].z,
        this.toPositions[i].z,
        this.animCurve.value(this.animTimeCount / this.animDuration),
      );
      this.blastModes[i].setLocalPosition(s);
      this.currentPositions[i] = s;
    }
    this.whiteBGFadeActivated &&
      ((this.whiteBG.resource.opacity = this.whiteBGFadeIn
        ? (2 * this.animTimeCount) / this.animDuration
        : 1 - (2 * this.animTimeCount) / this.animDuration),
      this.whiteBG.resource.update());
  }
};
BlastModel.prototype.controllerAnim = function (t, e) {
  var s = this;
  switch (
    ((this.currentState = e),
    (this.animTimeCount = 0),
    (this.fromPhoneCamAngle = this.currentPhoneCamAngle),
    this.clearTimer(),
    this.currentState)
  ) {
    case 0:
      break;
    case 1:
      this.isBlast = t;
      this.isGoToCamera = false;
      this.isBlast
        ? (this.resetRotation(this.blastPhoneRotate, 1, 0),
          this.resetCamRotation(this.blastPhoneCamRotate, 1, 0.5))
        : (this.resetRotation(this.beginPhoneAngle, 1, 0),
          this.resetCamRotation(this.beginPhoneCamAngle, 1, 0));
      this.resetPosition(this.beginPhonePosition, 1, 0);
      this.app.fire(
        "phone:hotspot_blast_detail",
        this.currentBlastHotIndex,
        false,
      );
      this.app.fire("cam_controllerCameraParam", t, this.currentState);
      this.whiteBGFadeActivated = false;
      break;
    case 2:
      this.isGoToCamera = t;
      this.isBlast = false;
      this.whiteBGFadeActivated = true;
      this.isGoToCamera
        ? ((this.whiteBGFadeIn = true),
          this.resetPosition(this.goToCameraPosition, 1, 0),
          this.resetRotation(this.goToCameraPhoneRotate, 1, 0))
        : (this.resetPosition(this.beginPhonePosition, 1, 0),
          this.resetRotation(this.beginPhoneAngle, 1, 0),
          (this.whiteBGFadeIn = false),
          (this.cameraHotspot.enabled = false));
      this.resetCamRotation(this.beginPhoneCamAngle, 1, 0);
      this.app.fire("phone:hotspot_camera_detail", 2);
      this.app.fire("cam_controllerCameraParam", t, this.currentState);
      break;
    case 3:
      if (
        ((this.is50x = t),
        (this.isBlast = false),
        (this.isGoToCamera = false),
        this.is50x)
      ) {
        this.app.fire("cam_controllerCameraParam", t, this.currentState);
        this.resetPosition(this.fivetyCameraPosition, 2.5, 0);
        this.timerFade1 = setTimeout(function () {
          s.app.fire("background_fade", 3);
        }, 2300);
        this.cam1 &&
          this.cam2 &&
          ((s.timer2 = setTimeout(function () {
            s.cam1.enabled = false;
            s.cam2.enabled = true;
            s.cam2Move(s.cam2Position_0, 3.2, 0);
            s.app.fire("cameraLight:start");
          }, 2450)),
          (s.timer3 = setTimeout(function () {
            s.cam1.enabled = true;
            s.cam2.enabled = false;
            s.app.fire("cameraLight:stop");
          }, 6550)));
        this.timerFade2 = setTimeout(function () {
          s.app.fire("background_fade", 3);
          s.resetPosition(s.beginPhonePosition, 1, 0);
          s.app.fire("cam_outSetCameraPan");
        }, 6400);
        this.timer4 = setTimeout(function () {
          s.app.fire("cam_controllerCameraParam", t, s.currentState);
          for (var e = 0; e < s.multipleModels.length; e++)
            s.multipleModels[e].enabled = true;
        }, 6550);
      } else {
        false === this.cam1.enabled && (this.cam1.enabled = true);
        this.cam2.enabled && (this.cam2.enabled = false);
        this.app.fire("cameraLight:stop");
        for (var o = 0; o < s.multipleModels.length; o++)
          this.multipleModels[o].enabled = false;
        this.resetPosition(this.beginPhonePosition, 1, 0);
        this.app.fire("cam_controllerCameraParam", t, this.currentState);
      }
  }
  for (i = 0; i < this.blastModes.length; i++) {
    this.fromPositions[i] = this.currentPositions[i];
    this.isBlast
      ? (this.toPositions[i] = this.endPositions[i])
      : (this.toPositions[i] = this.beginPositions[i]);
  }
  if (false === this.isBlast) {
    for (var a = 0; a < this.hotspotBlastEntitys.length; a++)
      this.hotspotBlastEntitys[a].enabled = this.isBlast;
    this.hotspotBlastOtherOne.enabled = this.isBlast;
  }
  this.app.fire("controllerPanToggle", this.isBlast);
  this.isStopAnim = true;
};
BlastModel.prototype.clearTimer = function () {
  this.timer1 && clearTimeout(this.timer1);
  this.timer2 && clearTimeout(this.timer2);
  this.timer2 && clearTimeout(this.timer2);
  this.timer3 && clearTimeout(this.timer3);
  this.timer4 && clearTimeout(this.timer4);
  this.timer5 && clearTimeout(this.timer5);
  this.timer6 && clearTimeout(this.timer6);
  this.timer7 && clearTimeout(this.timer7);
  this.timerFade1 && clearTimeout(this.timerFade1);
  this.timerFade2 && clearTimeout(this.timerFade2);
  this.cam2Timer1 && clearTimeout(this.cam2Timer1);
  this.cam2Timer2 && clearTimeout(this.cam2Timer2);
  this.cam2Timer3 && clearTimeout(this.cam2Timer3);
};
BlastModel.prototype.cam2Move = function (t, e, i) {
  this.cam2PositionTween && this.cam2PositionTween.stop();
  this.cam2.setLocalPosition(this.cam2BeginPosition);
  this.cam2PositionTween = this.cam2
    .tween(this.cam2.getLocalPosition())
    .to(t, e, pc.SineInOut)
    .delay(i);
  this.cam2PositionTween.start();
};
BlastModel.prototype.resetRotation = function (t, e, i) {
  this.currentPhoneAngle = this.phone.getLocalEulerAngles().clone();
  this.rotateTween && this.rotateTween.stop();
  this.phone.setLocalEulerAngles(this.currentPhoneAngle);
  this.rotateTween = this.phone
    .tween(this.phone.getLocalEulerAngles())
    .rotate(t, e, pc.SineInOut)
    .delay(i);
  this.rotateTween.start();
};
BlastModel.prototype.resetPosition = function (t, e, i) {
  this.currentPhonePosition = this.phone.getLocalPosition().clone();
  this.positionTween && this.positionTween.stop();
  this.phone.setLocalPosition(this.currentPhonePosition);
  this.positionTween = this.phone
    .tween(this.phone.getLocalPosition())
    .to(t, e, pc.SineInOut)
    .delay(i);
  this.positionTween.start();
};
BlastModel.prototype.resetCamRotation = function (t, e, i) {
  this.currentPhoneCamAngle = this.phoneCamera.getLocalEulerAngles().clone();
  this.camRotationTween && this.camRotationTween.stop();
  this.phoneCamera.setLocalEulerAngles(this.currentPhoneCamAngle);
  this.camRotationTween = this.phoneCamera
    .tween(this.phoneCamera.getLocalEulerAngles())
    .rotate(t, e, pc.SineInOut)
    .delay(i);
  this.camRotationTween.start();
};
BlastModel.prototype.controllerBlastHotspotDetail = function (t, e) {
  e
    ? (1 != t
        ? ((this.hotspotBlastDetails[t].enabled =
            !this.hotspotBlastDetails[t].enabled),
          this.currentBlastHotIndex >= 0 &&
            this.currentBlastHotIndex != t &&
            (1 != this.currentBlastHotIndex
              ? (this.hotspotBlastDetails[this.currentBlastHotIndex].enabled =
                  false)
              : ((this.hotspotBlastDetails[1].enabled = false),
                (this.hotspotBlastOtherOneDetail.enabled = false))))
        : ((this.hotspotBlastDetails[1].enabled =
            !this.hotspotBlastDetails[1].enabled),
          (this.hotspotBlastOtherOneDetail.enabled =
            !this.hotspotBlastOtherOneDetail.enabled),
          this.currentBlastHotIndex >= 0 &&
            1 != this.currentBlastHotIndex &&
            this.currentBlastHotIndex != t &&
            (this.hotspotBlastDetails[this.currentBlastHotIndex].enabled =
              false)),
      (this.currentBlastHotIndex = t),
      this.webEvent(this.hotspotBlastDetails[t].enabled, t))
    : (t >= 0
        ? 1 != t
          ? ((this.hotspotBlastDetails[t].enabled = false),
            this.webEvent(false, t))
          : ((this.hotspotBlastDetails[1].enabled = false),
            (this.hotspotBlastOtherOneDetail.enabled = false))
        : ((this.hotspotBlastDetails[0].enabled = false),
          this.webEvent(false, 0)),
      (this.currentBlastHotIndex = -1));
};
BlastModel.prototype.webEvent = function (t, e) {
  window.parent && window.parent.funcHotA && window.parent.funcHotA(t, e + 1);
};
