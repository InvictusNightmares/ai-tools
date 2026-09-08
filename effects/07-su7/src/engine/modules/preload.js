import { defineField as B } from "../fields.js";
// Recovered runtime module; preserve lazy initialization for cyclic dependencies.
export default (t, n, r) => {
  r.d(n, {
    Y: () => g,
  });
  var s = r(25),
    h = r(282);
  const l = {
    x: 0.5,
    y: 0.5,
  };
  class g {
    constructor(A, m) {
      B(this, "json");
      B(this, "texture");
      B(this, "_spriteFrames", {});
      B(this, "_animations", {});
      ((this.json = A), (this.texture = m));
      let D = A.meta.size,
        U = A.meta.scale / Math.max(D.w, D.h),
        R = A.frames;
      for (let ne in R) {
        let { frame: ce, sourceSize: xe, spriteSourceSize: Se, anchor: $ } = R[ne],
          q = ce.x / D.w,
          N = ce.y / D.h,
          ie = ce.w / D.w,
          _e = ce.h / D.h,
          Pe = xe,
          Be = Se,
          Re = $ || l,
          ct = U;
        this._spriteFrames[ne] = new h.X(
          m,
          new s.Ltg(q, 1 - (N + _e), ie, _e),
          new s.Ltg(
            Be.x + 0.5 * Be.w - Pe.w * Re.x,
            -(Be.y + 0.5 * Be.h - Pe.h * Re.y),
            Be.w,
            Be.h,
          ).multiplyScalar(ct),
        );
      }
      for (let ne in A.animations)
        this._animations[ne] = A.animations[ne].map((ce) => this._spriteFrames[ce]);
    }
    getAnimation(A) {
      return this._animations[A];
    }
    getSpriteFrame(A) {
      return this._spriteFrames[A];
    }
  }
};
