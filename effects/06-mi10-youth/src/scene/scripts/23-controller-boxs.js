/* Scene behavior: controller-boxs. Registered in original execution order. */
var ControllerBoxs = pc.createScript("controllerBoxs");
ControllerBoxs.attributes.add("boxMaterial", {
  type: "asset",
  assetType: "material",
  title: "盒子材质",
});
ControllerBoxs.attributes.add("boxTextures", {
  type: "asset",
  assetType: "texture",
  array: true,
  title: "盒子贴图",
});
ControllerBoxs.attributes.add("boxPlane1", {
  type: "entity",
  array: true,
  title: "盒子眼睛1",
});
ControllerBoxs.attributes.add("boxPlane2", {
  type: "entity",
  title: "盒子眼睛2",
});
ControllerBoxs.attributes.add("boxPlane3", {
  type: "entity",
  title: "盒子眼睛3",
});
ControllerBoxs.attributes.add("boxPlane4", {
  type: "entity",
  title: "盒子眼睛4",
});
ControllerBoxs.attributes.add("boxPlane5", {
  type: "entity",
  array: true,
  title: "盒子眼睛5",
});
ControllerBoxs.attributes.add("boxPlaneChangeVec3", {
  type: "vec3",
  array: true,
  title: "眼睛变化参数",
});
ControllerBoxs.prototype.initialize = function () {
  var e = pc.math.random(-1, 5),
    t = parseInt(e);
  this.beginBoxPlane2Position = this.boxPlane2.getLocalPosition().clone();
  this.beginBoxPlane3Position = this.boxPlane3.getLocalPosition().clone();
  this.beginBoxPlane4Position = this.boxPlane4.getLocalPosition().clone();
  this.beginBoxPlane5Scale = this.boxPlane5[0].getLocalScale().clone();
  this.currentEyeIndex = t;
  this.animTimeCount = 0;
  this.isFadeOut = false;
  this.isPlayEye = false;
  this.animScale = 2;
  this.isYoYo = true;
  this.delayTimeCount = 0;
  this.delayTimeDuration = 0.5;
  this.isDelay = true;
  this.app.on("box:fadeOutEye", this.fadeOutEye, this);
  this.app.on("box:switchTexture", this.switchTexture, this);
  this.switchTexture(t);
};
ControllerBoxs.prototype.update = function (e) {
  if (false !== this.entity.enabled)
    if (this.isFadeOut) {
      if (0.65 * this.animTimeCount > 1) {
        this.boxPlane1[0].enabled = false;
        this.boxPlane1[1].enabled = false;
        this.boxPlane2.enabled = false;
        this.boxPlane3.enabled = false;
        this.boxPlane4.enabled = false;
        this.boxPlane5[0].enabled = false;
        this.boxPlane5[1].enabled = false;
        this.isDelay = false;
        this.isPlayEye = false;
        this.isFadeOut = false;
      } else {
        this.animTimeCount += e;
        var t = 1 - pc.math.clamp(0.65 * this.animTimeCount, 0, 1);
        switch (this.currentEyeIndex) {
          case 0:
            this.boxPlane1[0].model.meshInstances[0].material.opacity = t;
            this.boxPlane1[0].model.meshInstances[0].material.update();
            this.boxPlane1[1].model.meshInstances[0].material.opacity = t;
            this.boxPlane1[1].model.meshInstances[0].material.update();
            break;
          case 1:
            this.boxPlane2.model.meshInstances[0].material.opacity = t;
            this.boxPlane2.model.meshInstances[0].material.update();
            break;
          case 2:
            this.boxPlane3.model.meshInstances[0].material.opacity = t;
            this.boxPlane3.model.meshInstances[0].material.update();
            break;
          case 3:
            this.boxPlane4.model.meshInstances[0].material.opacity = t;
            this.boxPlane4.model.meshInstances[0].material.update();
            break;
          case 4:
            this.boxPlane5[0].model.meshInstances[0].material.opacity = t;
            this.boxPlane5[0].model.meshInstances[0].material.update();
            this.boxPlane5[1].model.meshInstances[0].material.opacity = t;
            this.boxPlane5[1].model.meshInstances[0].material.update();
        }
      }
    } else if (
      (this.isDelay &&
        false === this.isPlayEye &&
        (this.delayTimeCount > this.delayTimeDuration
          ? ((this.delayTimeDuration = pc.math.random(0.4, 1)),
            (this.delayTimeCount = 0),
            (this.isPlayEye = true),
            (this.isDelay = false))
          : (this.delayTimeCount += e)),
      this.isPlayEye && false === this.isDelay)
    )
      if (this.animTimeCount * this.animScale > 1) {
        this.isYoYo = !this.isYoYo;
        this.isYoYo && ((this.isDelay = true), (this.isPlayEye = false));
        this.animScale = pc.math.random(1.9, 4);
        this.animTimeCount = 0;
      } else {
        this.animTimeCount += e;
        var a = pc.math.clamp(this.animTimeCount * this.animScale, 0, 1),
          i = new pc.Vec3();
        if (this.isYoYo)
          switch (this.currentEyeIndex) {
            case 1:
              i.x = pc.math.lerp(
                this.beginBoxPlane2Position.x,
                this.boxPlaneChangeVec3[1].x,
                a,
              );
              i.y = pc.math.lerp(
                this.beginBoxPlane2Position.y,
                this.boxPlaneChangeVec3[1].y,
                a,
              );
              i.z = pc.math.lerp(
                this.beginBoxPlane2Position.z,
                this.boxPlaneChangeVec3[1].z,
                a,
              );
              this.boxPlane2.setLocalPosition(i);
              break;
            case 2:
              i.x = pc.math.lerp(
                this.beginBoxPlane3Position.x,
                this.boxPlaneChangeVec3[2].x,
                a,
              );
              i.y = pc.math.lerp(
                this.beginBoxPlane3Position.y,
                this.boxPlaneChangeVec3[2].y,
                a,
              );
              i.z = pc.math.lerp(
                this.beginBoxPlane3Position.z,
                this.boxPlaneChangeVec3[2].z,
                a,
              );
              this.boxPlane3.setLocalPosition(i);
              break;
            case 3:
              i.x = pc.math.lerp(
                this.beginBoxPlane4Position.x,
                this.boxPlaneChangeVec3[3].x,
                a,
              );
              i.y = pc.math.lerp(
                this.beginBoxPlane4Position.y,
                this.boxPlaneChangeVec3[3].y,
                a,
              );
              i.z = pc.math.lerp(
                this.beginBoxPlane4Position.z,
                this.boxPlaneChangeVec3[3].z,
                a,
              );
              this.boxPlane4.setLocalPosition(i);
              break;
            case 4:
              i.x = pc.math.lerp(
                this.beginBoxPlane5Scale.x,
                this.boxPlaneChangeVec3[4].x,
                a,
              );
              i.y = pc.math.lerp(
                this.beginBoxPlane5Scale.y,
                this.boxPlaneChangeVec3[4].y,
                a,
              );
              i.z = pc.math.lerp(
                this.beginBoxPlane5Scale.z,
                this.boxPlaneChangeVec3[4].z,
                a,
              );
              this.boxPlane5[0].setLocalScale(i);
              this.boxPlane5[1].setLocalScale(i);
          }
        else
          switch (this.currentEyeIndex) {
            case 1:
              i.x = pc.math.lerp(
                this.boxPlaneChangeVec3[1].x,
                this.beginBoxPlane2Position.x,
                a,
              );
              i.y = pc.math.lerp(
                this.boxPlaneChangeVec3[1].y,
                this.beginBoxPlane2Position.y,
                a,
              );
              i.z = pc.math.lerp(
                this.boxPlaneChangeVec3[1].z,
                this.beginBoxPlane2Position.z,
                a,
              );
              this.boxPlane2.setLocalPosition(i);
              break;
            case 2:
              i.x = pc.math.lerp(
                this.boxPlaneChangeVec3[2].x,
                this.beginBoxPlane3Position.x,
                a,
              );
              i.y = pc.math.lerp(
                this.boxPlaneChangeVec3[2].y,
                this.beginBoxPlane3Position.y,
                a,
              );
              i.z = pc.math.lerp(
                this.boxPlaneChangeVec3[2].z,
                this.beginBoxPlane3Position.z,
                a,
              );
              this.boxPlane3.setLocalPosition(i);
              break;
            case 3:
              i.x = pc.math.lerp(
                this.boxPlaneChangeVec3[3].x,
                this.beginBoxPlane4Position.x,
                a,
              );
              i.y = pc.math.lerp(
                this.boxPlaneChangeVec3[3].y,
                this.beginBoxPlane4Position.y,
                a,
              );
              i.z = pc.math.lerp(
                this.boxPlaneChangeVec3[3].z,
                this.beginBoxPlane4Position.z,
                a,
              );
              this.boxPlane4.setLocalPosition(i);
              break;
            case 4:
              i.x = pc.math.lerp(
                this.boxPlaneChangeVec3[4].x,
                this.beginBoxPlane5Scale.x,
                a,
              );
              i.y = pc.math.lerp(
                this.boxPlaneChangeVec3[4].y,
                this.beginBoxPlane5Scale.y,
                a,
              );
              i.z = pc.math.lerp(
                this.boxPlaneChangeVec3[4].z,
                this.beginBoxPlane5Scale.z,
                a,
              );
              this.boxPlane5[0].setLocalScale(i);
              this.boxPlane5[1].setLocalScale(i);
          }
      }
};
ControllerBoxs.prototype.switchTexture = function (e) {
  this.boxMaterial.resource.diffuseMap = this.boxTextures[e].resource;
  this.boxMaterial.resource.update();
  this.boxPlane1[0].enabled = false;
  this.boxPlane1[1].enabled = false;
  this.boxPlane2.enabled = false;
  this.boxPlane3.enabled = false;
  this.boxPlane4.enabled = false;
  this.boxPlane5[0].enabled = false;
  this.boxPlane5[1].enabled = false;
  this.boxPlane1Anim && clearInterval(this.boxPlane1Anim);
  this.switchAnim(e);
  this.isYoYo = true;
  this.animTimeCount = 0;
};
ControllerBoxs.prototype.switchAnim = function (e) {
  var t = this;
  switch (((this.currentEyeIndex = e), e)) {
    case 0:
      this.boxPlane1[0].enabled = true;
      this.boxPlane1Anim = setInterval(
        (t.setEye1 = function () {
          t.boxPlane1[0].enabled
            ? ((t.boxPlane1[0].enabled = false),
              (t.boxPlane1[1].enabled = true))
            : ((t.boxPlane1[0].enabled = true),
              (t.boxPlane1[1].enabled = false));
        }),
        500,
      );
      break;
    case 1:
      this.boxPlane2.enabled = true;
      break;
    case 2:
      this.boxPlane3.enabled = true;
      break;
    case 3:
      this.boxPlane4.enabled = true;
      break;
    case 4:
      this.boxPlane5[0].enabled = true;
      this.boxPlane5[1].enabled = true;
  }
};
ControllerBoxs.prototype.fadeOutEye = function () {
  this.animTimeCount = 0;
  this.isFadeOut = true;
  clearInterval(this.boxPlane1Anim);
  this.eyeTween && this.eyeTween.stop();
};
