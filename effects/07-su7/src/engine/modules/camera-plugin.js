import { defineField as B } from "../fields.js";
// Recovered runtime module; preserve lazy initialization for cyclic dependencies.
export default (t, n, r) => {
  r.d(n, {
    k: () => A,
  });
  var s = r(879),
    h = r(585),
    l = r(861),
    g = r(25),
    _ = r(992);
  class A extends _.S {
    constructor(U) {
      super();
      B(this, "name", "VirtualCameraPlugin");
      B(this, "_brain", null);
      B(this, "_freelookCamera", null);
      this.onLoad = () => {
        const R = this.viewer.camera;
        ((this._brain = this.viewer.addComponent(R, s.W)),
          (this._freelookCamera = this.viewer.addNode(
            h.z,
            Object.assign(
              {
                fov: R.fov,
                near: R.near,
                far: R.far,
                lookAt: new g.Tme(),
                position: (0, l.nX)(0, 0, 4),
              },
              U,
            ),
          )));
      };
    }
    onEnable() {
      (this._brain && (this._brain.enabled = !0),
        this._freelookCamera && (this._freelookCamera.enabled = !0));
    }
    onDisable() {
      (this._brain && (this._brain.enabled = !1),
        this._freelookCamera && (this._freelookCamera.enabled = !1));
    }
  }
};
