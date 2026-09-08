import {
  Component,
  Tweening,
  ShaderMaterial,
  Vector3,
  Matrix4,
  Quaternion,
  PlaneGeometry,
  InstancedMesh,
} from "./../engine/index.js";
import { defineField as B } from "./../engine/fields.js";
import { resources } from "./../config/resources.js";
import { Ag, SA } from "./materials.js";
import { rl } from "./orbit.js";
class VisibilityController extends Component {
  constructor() {
    super(...arguments);
    B(this, "controller", null);
  }
  show(r = 1, s = 0) {
    (Tweening.TweenManager.KillTweensOf(this.controller),
      Tweening.TweenManager.Tween(this.controller)
        .delay(s)
        .to(
          {
            visibility: 1,
          },
          r,
        )
        .easing(Tweening.Easing.Cubic.InOut)
        .start());
  }
  hide(r = 1, s = 0) {
    (Tweening.TweenManager.KillTweensOf(this.controller),
      Tweening.TweenManager.Tween(this.controller)
        .delay(s)
        .to(
          {
            visibility: 0,
          },
          r,
        )
        .easing(Tweening.Easing.Cubic.InOut)
        .start());
  }
}
class DimensionsEffect extends VisibilityController {
  onLoad() {
    const { materials: n } = resources.sm_size.meshData;
    (this.viewer.addNode(resources.sm_size),
      (this.controller = new Proxy(
        {
          visibility: 1,
        },
        {
          set: (r, s, h) => (
            (r[s] = h),
            h >= 0.005 ? (resources.sm_size.visible = !0) : (resources.sm_size.visible = !1),
            Object.values(n).forEach((l) => {
              ((l.opacity = h), l instanceof ShaderMaterial && (l.uniforms.opacity.value = h));
            }),
            !0
          ),
        },
      )),
      (this.controller.visibility = 0));
  }
}
class CurvatureEffect extends VisibilityController {
  onLoad() {
    const { materials: n } = resources.sm_curvature.meshData;
    (this.viewer.addNode(resources.sm_curvature),
      (this.controller = new Proxy(
        {
          visibility: 1,
        },
        {
          set: (r, s, h) => (
            (r[s] = h),
            h >= 0.005
              ? (resources.sm_curvature.visible = !0)
              : (resources.sm_curvature.visible = !1),
            Object.values(n).forEach((l) => {
              ((l.opacity = h), l instanceof ShaderMaterial && (l.uniforms.opacity.value = h));
            }),
            !0
          ),
        },
      )),
      (this.controller.visibility = 0));
  }
}
class WindEffect extends VisibilityController {
  onLoad() {
    const { materials: n } = resources.sm_windspeed.meshData;
    (this.viewer.addNode(resources.sm_windspeed),
      (this.controller = new Proxy(
        {
          visibility: 1,
        },
        {
          set: (r, s, h) => (
            (r[s] = h),
            h >= 0.005
              ? (resources.sm_windspeed.visible = !0)
              : (resources.sm_windspeed.visible = !1),
            Object.values(n).forEach((l) => {
              ((l.opacity = h), l instanceof ShaderMaterial && (l.uniforms.opacity.value = h));
            }),
            !0
          ),
        },
      )),
      (this.controller.visibility = 0));
  }
}
class LineCarEffect extends VisibilityController {
  onLoad() {
    const { materials: n } = resources.sm_linecar.meshData;
    (this.viewer.addNode(resources.sm_linecar),
      (this.controller = new Proxy(
        {
          visibility: 1,
        },
        {
          set: (r, s, h) => (
            (r[s] = h),
            h >= 0.005 ? (resources.sm_linecar.visible = !0) : (resources.sm_linecar.visible = !1),
            Object.values(n).forEach((l) => {
              ((resources.u_car_discard.value = 1 - h),
                (l.opacity = h),
                l instanceof ShaderMaterial && (l.uniforms.opacity.value = h));
            }),
            !0
          ),
        },
      )),
      (this.controller.visibility = 0));
  }
}
class RadarEffect extends VisibilityController {
  onLoad() {
    const { materials: n } = resources.sm_carradar.meshData;
    (this.viewer.addNode(resources.sm_carradar),
      (this.controller = new Proxy(
        {
          visibility: 1,
        },
        {
          set: (r, s, h) => (
            (r[s] = h),
            (resources.u_floor_typeSwitch.value = h),
            h >= 0.005
              ? (resources.sm_carradar.visible = !0)
              : (resources.sm_carradar.visible = !1),
            Object.values(n).forEach((l) => {
              ((l.opacity = h), l instanceof ShaderMaterial && (l.uniforms.opacity.value = h));
            }),
            !0
          ),
        },
      )),
      (this.controller.visibility = 0));
  }
}
class TrafficEffect extends VisibilityController {
  constructor() {
    super(...arguments);
    B(this, "_length", 17);
    B(this, "_car1");
    B(this, "_car2");
    B(this, "_moveParams1", new Vector3());
    B(this, "_moveParams2", new Vector3());
  }
  onLoad() {
    ((this._car1 = resources.sm_simpleCar.children[0]),
      (this._car2 = this._car1.clone()),
      resources.sm_simpleCar.add(this._car2),
      this.viewer.addNode(resources.sm_simpleCar),
      (this.controller = new Proxy(
        {
          visibility: 1,
        },
        {
          set: (r, s, h) => (
            (r[s] = h),
            h >= 0.005
              ? (resources.sm_simpleCar.visible = !0)
              : (resources.sm_simpleCar.visible = !1),
            (Ag.opacity = h),
            !0
          ),
        },
      )),
      (this.controller.visibility = 0),
      this.randomUpdate(this._moveParams1, this._car1),
      this.randomUpdate(this._moveParams2, this._car2));
  }
  randomUpdate(r, s) {
    ((r.x = Math.random() > 0.5 ? -1 : 1),
      (r.y = Math.random() * 3 + 2.5),
      (r.z = Math.random() * 2 + 1),
      (s.position.x = this._length * -r.x));
  }
  update(r) {
    if (this._car1 && this._car2) {
      const s = this._car1.position;
      (s.set(s.x + r * this._moveParams1.z * this._moveParams1.x, s.y, this._moveParams1.y),
        resources.u_simpleCarCenter1.value.copy(s),
        Math.abs(s.x) > this._length && this.randomUpdate(this._moveParams1, this._car1));
      const h = this._car2.position;
      (h.set(h.x + r * this._moveParams2.z * this._moveParams2.x, s.y, -this._moveParams2.y),
        resources.u_simpleCarCenter2.value.copy(h),
        Math.abs(h.x) > this._length && this.randomUpdate(this._moveParams2, this._car2));
    }
  }
}
const Fd = [
    [0.65, 1.04, -1.16],
    [-0.35, 1.43, -0.69],
    [1.08, 0.72, -1.01],
    [1.95, 0.76, -1],
    [-1.66, 1.34, 0],
    [-1.95, 0.58, -1],
    [0.35, 1.44, -0.08],
    [0.26, 1.46, -0],
    [2.53, 0.45, -0.64],
    [2.73, 0.43, -0.3],
    [2.78, 0.43, -0],
    [-2.3, 0.67, -0.88],
    [-2.72, 0.68, 0],
    [-2.69, 0.62, -0.4],
    [-2.24, 0.53, -0.94],
    [0.65, 1.04, 1.16],
    [-0.35, 1.43, 0.69],
    [1.08, 0.72, 1.01],
    [1.95, 0.76, 1],
    [-1.95, 0.58, 1],
    [0.35, 1.44, 0.08],
    [2.53, 0.45, 0.64],
    [2.73, 0.43, 0.3],
    [-2.3, 0.67, 0.88],
    [-2.69, 0.62, 0.4],
    [-2.24, 0.53, 0.94],
    [2.62, 0.43, 0.4],
    [-2.69, 0.62, -0.4],
  ],
  MA = new Matrix4(),
  CA = new Vector3(),
  oB = new Quaternion(),
  aB = new Vector3(1, 1, 1);
class SensorPoints extends VisibilityController {
  onLoad() {
    const n = new PlaneGeometry(0.1, 0.1),
      r = new InstancedMesh(n, SA, Fd.length);
    for (let s = 0; s < Fd.length; s++)
      (CA.set(Fd[s][0], Fd[s][1], Fd[s][2]), MA.compose(CA, oB, aB), r.setMatrixAt(s, MA));
    ((r.instanceMatrix.needsUpdate = !0),
      this.viewer.scene.add(r),
      (this.controller = new Proxy(
        {
          visibility: 1,
        },
        {
          set: (s, h, l) => (
            (s[h] = l),
            l >= 0.005 ? (r.visible = !0) : (r.visible = !1),
            (SA.uniforms.opacity.value = l),
            !0
          ),
        },
      )),
      (this.controller.visibility = 0));
  }
}
const PA = new Vector3();
class MovingSensor extends VisibilityController {
  constructor() {
    super(...arguments);
    B(this, "_originPos", new Vector3());
    B(this, "_originRotZ", 0);
    B(this, "_targetPos", new Vector3(-2.3626, 1.1511, 0));
    B(this, "_targetRotZ", (-12.9 / 360) * Math.PI * 2);
  }
  onLoad() {
    const r = resources.sm_car.children[0].children.find((s) => s.name == "WeiYi");
    (this._originPos.copy(r.position),
      (this._originRotZ = r.rotation.z),
      (this.controller = new Proxy(
        {
          visibility: 1,
        },
        {
          set: (s, h, l) => (
            (s[h] = l),
            PA.copy(this._originPos).lerp(this._targetPos, l),
            r.position.copy(PA),
            (r.rotation.z = rl(this._originRotZ, this._targetRotZ, l)),
            !0
          ),
        },
      )),
      (this.controller.visibility = 0));
  }
}
export {
  VisibilityController,
  DimensionsEffect,
  CurvatureEffect,
  WindEffect,
  LineCarEffect,
  RadarEffect,
  TrafficEffect,
  Fd,
  MA,
  CA,
  oB,
  aB,
  SensorPoints,
  PA,
  MovingSensor,
};
