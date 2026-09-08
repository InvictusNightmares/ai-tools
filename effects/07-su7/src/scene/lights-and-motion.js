import { Color, Component, InputEvents, Vector3 } from "./../engine/index.js";
import { defineField as B } from "./../engine/fields.js";
import { events, ShowState } from "./../state/events.js";
import { rl } from "./orbit.js";
import { resources } from "./../config/resources.js";
const TA = new Color("#000000"),
  QO = new Color("#000000"),
  KO = new Color("#ffffff");
class HeadlightController extends Component {
  constructor(r) {
    super();
    B(this, "_lightMaterial");
    B(this, "_lightValue", 0);
    this.onLoad = () => {
      ((this._lightMaterial = r.meshData.materials.Car_ight),
        (this._lightMaterial.toneMapped = !1),
        (this._lightMaterial.aoMapIntensity = 0),
        (this._lightMaterial.color = TA),
        (this._lightMaterial.needsUpdate = !0));
    };
  }
  set lightValue(r) {
    ((this._lightValue = r), TA.copy(QO).lerp(KO, r));
  }
  get lightValue() {
    return this._lightValue;
  }
}
class TaillightController extends Component {
  constructor(r) {
    super();
    B(this, "_lightMaterial");
    this.onLoad = () => {
      ((this._lightMaterial = r.meshData.materials.light),
        this._lightMaterial.emissive.setRGB(0, 0, 0),
        (this._lightMaterial.transparent = !0),
        (this._lightMaterial.depthWrite = !1),
        (this._lightMaterial.needsUpdate = !0),
        (this.opacity = 1));
    };
  }
  get lightEmissiveIntensity() {
    return this._lightMaterial.emissiveIntensity;
  }
  set lightEmissiveIntensity(r) {
    this._lightMaterial.emissiveIntensity = r;
  }
  get lightEmissiveColor() {
    return this._lightMaterial.emissive;
  }
  set lightEmissiveColor(r) {
    this._lightMaterial.emissive.copy(r);
  }
  get opacity() {
    return this._lightMaterial.opacity;
  }
  set opacity(r) {
    this._lightMaterial.opacity = r;
  }
}
class PointerEffects extends Component {
  onEnable() {
    (this.viewer.on(InputEvents.POINTER_DOWN, this._onPointerDown, this),
      this.viewer.on(InputEvents.POINTER_UP, this._onPointerUp, this));
  }
  onDisable() {
    (this.viewer.off(InputEvents.POINTER_DOWN, this._onPointerDown, this),
      this.viewer.off(InputEvents.POINTER_UP, this._onPointerUp, this));
  }
  _onPointerDown() {
    events.emit(events.CLICKEFFECT, !0);
  }
  _onPointerUp() {
    events.emit(events.CLICKEFFECT, !1);
  }
}
const EA = new Vector3();
class WheelMotion extends Component {
  constructor(r, s) {
    super();
    B(this, "_wheels");
    B(this, "_targetVelocity", 0);
    B(this, "_currentVelocity", 0);
    B(this, "_lerpStrength", 1);
    B(this, "_springCameraOB");
    this.onLoad = () => {
      const h = r.children[0].children.find((l) => l.name == "Wheel");
      ((this._wheels = h), (this._springCameraOB = s));
    };
  }
  set targetVelocity(r) {
    this._targetVelocity = r;
  }
  set lerpStrength(r) {
    this._lerpStrength = r;
  }
  update(r) {
    this._currentVelocity = rl(this._currentVelocity, this._targetVelocity, r * this._lerpStrength);
    for (const h of this._wheels.children)
      h.rotateZ(((-this._currentVelocity * r) / (Math.PI * 0.737774)) * 2 * Math.PI);
    resources.u_floorUVOffset.value.x += this._currentVelocity * r;
    let s = resources.u_speedUpBackgroundValue.value;
    (events.currentShowingState == ShowState.State1
      ? (s = rl(s, this._currentVelocity, r * 2))
      : (s = rl(s, 0, r * 5)),
      (resources.u_speedUpBackgroundValue.value = s),
      EA.set(1, 1, 1).multiplyScalar(s / 5),
      this._springCameraOB._springCamera.positionScale.copy(EA),
      s < 0.1 ? (resources.sm_speedup.visible = !1) : (resources.sm_speedup.visible = !0));
  }
}
export { TA, QO, KO, HeadlightController, TaillightController, PointerEffects, EA, WheelMotion };
