import {
  Vector3,
  Euler,
  Quaternion,
  rM,
  Component,
  MathUtils,
  Tweening,
  Sv,
  inspectProperty,
} from "./../engine/index.js";
import { defineField as B } from "./../engine/fields.js";
var xO = Object.defineProperty,
  bO = Object.getOwnPropertyDescriptor,
  Ic = (t, n, r, s) => {
    for (var h = s > 1 ? void 0 : s ? bO(n, r) : n, l = t.length - 1, g; l >= 0; l--)
      (g = t[l]) && (h = (s ? g(n, r, h) : g(h)) || h);
    return (s && h && xO(n, r, h), h);
  };
const vA = new Vector3(),
  Tv = new Euler(),
  wO = new Quaternion(),
  AO = rM();
class SpringCamera extends Component {
  constructor({
    near: r = 0.01,
    far: s = 100,
    fov: h = 45,
    rotation: l = new Euler(0, -Math.PI / 2, 0),
    lookAt: g = new Vector3(),
    springLength: _ = 2,
  }) {
    super();
    B(this, "enablePositionNoise", !0);
    B(this, "positionFrequency", 1.5);
    B(this, "positionAmplitude", 0.04);
    B(this, "positionScale", rM(1));
    B(this, "positionFractalLevel", 3);
    B(this, "_time", []);
    B(this, "_fbmNorm", 1 / 0.75);
    B(this, "_springLength", 2);
    B(this, "_lookAt", new Vector3(0, 0.23686, 0));
    B(this, "rotation", new Euler(0, -Math.PI / 2, 0));
    B(this, "targetCameraPosition", new Vector3());
    this.onLoad = () => {
      ((this.viewer.camera.near = r),
        (this.viewer.camera.far = s),
        (this.viewer.camera.fov = h),
        this.viewer.camera.updateProjectionMatrix(),
        this.rotation.copy(l),
        this._lookAt.copy(g),
        (this._springLength = _),
        this.calculateCameraPosition(),
        this.viewer.camera.position.copy(this.targetCameraPosition),
        this.viewer.camera.lookAt(this._lookAt),
        this.rehash());
    };
  }
  rehash() {
    for (let r = 0; r < 6; r++) this._time[r] = MathUtils.randFloat(-1e4, 0);
  }
  get springLength() {
    return this._springLength;
  }
  set springLength(r) {
    this._springLength = r;
  }
  get __rotation() {
    return this.rotation;
  }
  set __rotation(r) {
    this.rotation.copy(r);
  }
  get lookAt() {
    return this._lookAt;
  }
  set lookAt(r) {
    this._lookAt.copy(r);
  }
  gotoPOI(r, s, h, l = 1.5, g = Tweening.Easing.Cubic.InOut, _ = 0) {
    return new Promise((A) => {
      const m = new Quaternion().setFromEuler(this.rotation),
        D = new Quaternion();
      (Tweening.TweenManager.KillTweensOf(this),
        Tweening.TweenManager.Tween(this)
          .to(
            {
              lookAt: r,
              springLength: s,
            },
            l,
          )
          .delay(_)
          .onUpdate((U, R) => {
            const ne = wO.setFromEuler(h);
            (D.copy(m).slerp(ne, g(R)), this.rotation.copy(Tv.setFromQuaternion(D, "YZX")));
          })
          .easing(g)
          .start()
          .onComplete(() => {
            A(!0);
          }));
    });
  }
  calculateCameraPosition() {
    (Tv.set(0, this.rotation.y, this.rotation.z),
      vA.set(1, 0, 0).applyEuler(Tv).multiplyScalar(this._springLength).add(this._lookAt),
      this.targetCameraPosition.copy(vA));
  }
  update(r) {
    if (
      (this.calculateCameraPosition(),
      this.viewer.camera.position.copy(this.targetCameraPosition),
      this.viewer.camera.lookAt(this._lookAt),
      this.enablePositionNoise)
    ) {
      for (let h = 0; h < 3; h++) this._time[h] += this.positionFrequency * r;
      let s = AO.set(
        Sv.Fbm(this.positionFractalLevel, this._time[0]),
        Sv.Fbm(this.positionFractalLevel, this._time[1]),
        Sv.Fbm(this.positionFractalLevel, this._time[2]),
      );
      ((s = s.multiply(this.positionScale)),
        s.multiplyScalar(this.positionAmplitude * this._fbmNorm),
        this.viewer.camera.position.add(s));
    }
  }
}
Ic(
  [
    inspectProperty({
      dir: "position",
    }),
  ],
  SpringCamera.prototype,
  "enablePositionNoise",
  2,
);
Ic(
  [
    inspectProperty({
      dir: "position",
    }),
  ],
  SpringCamera.prototype,
  "positionFrequency",
  2,
);
Ic(
  [
    inspectProperty({
      dir: "position",
    }),
  ],
  SpringCamera.prototype,
  "positionAmplitude",
  2,
);
Ic(
  [
    inspectProperty({
      dir: "position",
    }),
  ],
  SpringCamera.prototype,
  "positionScale",
  2,
);
Ic(
  [
    inspectProperty({
      dir: "position",
      min: 0,
      max: 8,
      step: 1,
    }),
  ],
  SpringCamera.prototype,
  "positionFractalLevel",
  2,
);
Ic([inspectProperty()], SpringCamera.prototype, "springLength", 1);
Ic([inspectProperty()], SpringCamera.prototype, "__rotation", 1);
Ic([inspectProperty()], SpringCamera.prototype, "lookAt", 1);
new Quaternion();
new Vector3();
export { xO, bO, Ic, vA, Tv, wO, AO, SpringCamera };
