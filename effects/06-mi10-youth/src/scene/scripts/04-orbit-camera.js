/* Scene behavior: orbit-camera. Registered in original execution order. */
var OrbitCamera = pc.createScript("orbitCamera");
OrbitCamera.attributes.add("distanceMax", {
  type: "number",
  default: 5,
  title: "Distance Max",
  description: "Setting this at 0 will give an infinite distance limit",
});
OrbitCamera.attributes.add("distanceMin", {
  type: "number",
  default: 3,
  title: "Distance Min",
});
OrbitCamera.attributes.add("pitchAngleMax", {
  type: "number",
  default: 90,
  title: "Pitch Angle Max (degrees)",
});
OrbitCamera.attributes.add("pitchAngleMin", {
  type: "number",
  default: -90,
  title: "Pitch Angle Min (degrees)",
});
OrbitCamera.attributes.add("inertiaFactor", {
  type: "number",
  default: 0,
  title: "Inertia Factor",
  description:
    "Higher value means that the camera will continue moving after the user has stopped dragging. 0 is fully responsive.较高的值表示用户停止拖动后，相机将继续移动。 0完全响应",
});
OrbitCamera.attributes.add("focusEntity", {
  type: "entity",
  title: "Focus Entity",
  description:
    "Entity for the camera to focus on. If blank, then the camera will use the whole scene 相机要聚焦的实体。 如果为空白，则相机将使用整个场景",
});
OrbitCamera.attributes.add("frameOnStart", {
  type: "boolean",
  default: false,
  title: "Frame on Start",
  description:
    'Frames the entity or scene at the start of the application. 在应用程序开始时构图实体或场景"',
});
OrbitCamera.attributes.add("panning", {
  type: "boolean",
  default: false,
});
Object.defineProperty(OrbitCamera.prototype, "distance", {
  get: function () {
    return this._targetDistance;
  },
  set: function (t) {
    this._targetDistance = this._clampDistance(t);
  },
});
Object.defineProperty(OrbitCamera.prototype, "pitch", {
  get: function () {
    return this._targetPitch;
  },
  set: function (t) {
    this._targetPitch = this._clampPitchAngle(t);
  },
});
Object.defineProperty(OrbitCamera.prototype, "yaw", {
  get: function () {
    return this._targetYaw;
  },
  set: function (t) {
    this._targetYaw = t;
    var i = (this._targetYaw - this._yaw) % 360;
    this._targetYaw =
      i > 180
        ? this._yaw - (360 - i)
        : i < -180
          ? this._yaw + (360 + i)
          : this._yaw + i;
  },
});
Object.defineProperty(OrbitCamera.prototype, "pivotPoint", {
  get: function () {
    return this._pivotPoint;
  },
  set: function (t) {
    this._pivotPoint.copy(t);
  },
});
OrbitCamera.prototype.focus = function (t) {
  this._buildAabb(t, 0);
  var i = this._modelsAabb.halfExtents,
    e = Math.max(i.x, Math.max(i.y, i.z));
  e /= Math.tan(0.5 * this.entity.camera.fov * pc.math.DEG_TO_RAD);
  e *= 2;
  this.distance = e;
  this._removeInertia();
  this._pivotPoint.copy(this._modelsAabb.center);
};
OrbitCamera.distanceBetween = new pc.Vec3();
OrbitCamera.prototype.resetAndLookAtPoint = function (t, i) {
  this.pivotPoint.copy(i);
  this.entity.setPosition(t);
  this.entity.lookAt(i);
  var e = OrbitCamera.distanceBetween;
  e.sub2(i, t);
  this.distance = e.length();
  this.pivotPoint.copy(i);
  var a = this.entity.getRotation();
  this.yaw = this._calcYaw(a);
  this.pitch = this._calcPitch(a, this.yaw);
  this._removeInertia();
  this._updatePosition();
};
OrbitCamera.prototype.resetAndLookAtEntity = function (t, i) {
  this._buildAabb(i, 0);
  this.resetAndLookAtPoint(t, this._modelsAabb.center);
};
OrbitCamera.prototype.reset = function (t, i, e) {
  this.pitch = i;
  this.yaw = t;
  this.distance = e;
  this._removeInertia();
};
OrbitCamera.prototype.initialize = function () {
  var t = this,
    i = function () {
      t._checkAspectRatio();
    };
  window.addEventListener("resize", i, false);
  this._checkAspectRatio();
  this._modelsAabb = new pc.BoundingBox();
  this._buildAabb(this.focusEntity || this.app.root, 0);
  this.entity.lookAt(this._modelsAabb.center);
  this._pivotPoint = new pc.Vec3();
  this._pivotPoint.copy(this._modelsAabb.center);
  var e = this.entity.getRotation();
  if (
    ((this._yaw = this._calcYaw(e)),
    (this._pitch = this._clampPitchAngle(this._calcPitch(e, this._yaw))),
    this.entity.setLocalEulerAngles(this._pitch, this._yaw, 0),
    (this._distance = 0),
    (this._targetYaw = this._yaw),
    (this._targetPitch = this._pitch),
    this.frameOnStart)
  )
    this.focus(this.focusEntity || this.app.root);
  else {
    var a = new pc.Vec3();
    a.sub2(this.entity.getPosition(), this._pivotPoint);
    this._distance = this._clampDistance(a.length());
  }
  this._targetDistance = this._distance;
  this.on("attr:distanceMin", function (t, i) {
    this._targetDistance = this._clampDistance(this._distance);
  });
  this.on("attr:distanceMax", function (t, i) {
    this._targetDistance = this._clampDistance(this._distance);
  });
  this.on("attr:pitchAngleMin", function (t, i) {
    this._targetPitch = this._clampPitchAngle(this._pitch);
  });
  this.on("attr:pitchAngleMax", function (t, i) {
    this._targetPitch = this._clampPitchAngle(this._pitch);
  });
  this.on("attr:focusEntity", function (t, i) {
    this.frameOnStart
      ? this.focus(t || this.app.root)
      : this.resetAndLookAtEntity(
          this.entity.getPosition(),
          t || this.app.root,
        );
  });
  this.on("attr:frameOnStart", function (t, i) {
    t && this.focus(this.focusEntity || this.app.root);
  });
  this.on("destroy", function () {
    window.removeEventListener("resize", i, false);
  });
};
OrbitCamera.prototype.update = function (t) {
  var i = 0 === this.inertiaFactor ? 1 : Math.min(t / this.inertiaFactor, 1);
  this._distance = pc.math.lerp(this._distance, this._targetDistance, i);
  this._yaw = pc.math.lerp(this._yaw, this._targetYaw, i);
  this._pitch = pc.math.lerp(this._pitch, this._targetPitch, i);
  this._updatePosition();
};
OrbitCamera.prototype._updatePosition = function () {
  this.entity.setLocalPosition(0, 0, 0);
  this.entity.setLocalEulerAngles(this._pitch, this._yaw, 0);
  var t = this.entity.getPosition();
  t.copy(this.entity.forward);
  t.scale(-this._distance);
  t.add(this.pivotPoint);
  this.entity.setPosition(t);
};
OrbitCamera.prototype._removeInertia = function () {
  this._yaw = this._targetYaw;
  this._pitch = this._targetPitch;
  this._distance = this._targetDistance;
};
OrbitCamera.prototype._checkAspectRatio = function () {
  var t = this.app.graphicsDevice.height,
    i = this.app.graphicsDevice.width;
  this.entity.camera.horizontalFov = t > i;
};
OrbitCamera.prototype._buildAabb = function (t, i) {
  var e = 0;
  for (e = 0; e < t.children.length; ++e)
    i += this._buildAabb(t.children[e], i);
  return i;
};
OrbitCamera.prototype._calcYaw = function (t) {
  var i = new pc.Vec3();
  return (
    t.transformVector(pc.Vec3.FORWARD, i),
    Math.atan2(-i.x, -i.z) * pc.math.RAD_TO_DEG
  );
};
OrbitCamera.prototype._clampDistance = function (t) {
  return this.distanceMax > 0
    ? pc.math.clamp(t, this.distanceMin, this.distanceMax)
    : Math.max(t, this.distanceMin);
};
OrbitCamera.prototype._clampPitchAngle = function (t) {
  return pc.math.clamp(t, -this.pitchAngleMax, -this.pitchAngleMin);
};
OrbitCamera.quatWithoutYaw = new pc.Quat();
OrbitCamera.yawOffset = new pc.Quat();
OrbitCamera.prototype._calcPitch = function (t, i) {
  var e = OrbitCamera.quatWithoutYaw,
    a = OrbitCamera.yawOffset;
  a.setFromEulerAngles(0, -i, 0);
  e.mul2(a, t);
  var n = new pc.Vec3();
  return (
    e.transformVector(pc.Vec3.FORWARD, n),
    Math.atan2(n.y, -n.z) * pc.math.RAD_TO_DEG
  );
};
