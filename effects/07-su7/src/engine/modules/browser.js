import { defineField as B } from "../fields.js";
// Recovered runtime module; preserve lazy initialization for cyclic dependencies.
export default (t, n, r) => {
  r.d(n, {
    S: () => _,
    v: () => A,
  });
  var s = r(25);
  const { lerp: h, clamp01: l } = s.MathUtils;
  function g(m, D, U, R, ne) {
    const ce = (R - D) * 0.5,
      xe = (ne - U) * 0.5,
      Se = m * m,
      $ = m * Se;
    return (2 * U - 2 * R + ce + xe) * $ + (-3 * U + 3 * R - 2 * ce - xe) * Se + ce * m + U;
  }
  class _ {
    constructor(D = 0, U = 0, R = 0) {
      B(this, "x");
      B(this, "y");
      B(this, "mode", 0);
      (this.set(D, U), (this.mode = R));
    }
    set(D, U) {
      return ((this.x = D), (this.y = U), this);
    }
    lerp(D, U, R = this) {
      return ((R.x = h(this.x, D.x, U)), (R.y = h(this.y, D.y, U)), R);
    }
  }
  class A {
    constructor(D = "", U = [new _(0, 0), new _(1, 1)]) {
      B(this, "name");
      B(this, "points");
      B(this, "isAnimationCurve", !0);
      B(this, "needsUpdate", !0);
      B(this, "_samples", 100);
      B(
        this,
        "_interpolant",
        new s.lfu(new Float32Array(100), new Float32Array(100), 1, new Float32Array(100)),
      );
      ((this.name = D), (this.points = U));
    }
    _getInterpolant(D) {
      return (
        this._samples !== D &&
          ((this._samples = D),
          (this._interpolant = new s.lfu(
            new Float32Array(D),
            new Float32Array(D),
            1,
            new Float32Array(D),
          ))),
        this._interpolant
      );
    }
    resample(D = 100) {
      const U = 1 / (D - 1),
        R = this._getInterpolant(D),
        ne = R.parameterPositions,
        ce = R.sampleValues,
        xe = new _();
      for (let Se = 0; Se < D; Se++) (this.getPoint(Se * U, xe), (ne[Se] = xe.x), (ce[Se] = xe.y));
    }
    evaluate(D) {
      return (
        this.needsUpdate && ((this.needsUpdate = !1), this.resample()),
        this._interpolant.evaluate(D)[0]
      );
    }
    getPoint(D, U) {
      const R = this.points;
      if (D <= 0) return U.set(D, R[0].y);
      if (D >= 1) return U.set(D, R[R.length - 1].y);
      const ne = (R.length - 1) * D,
        ce = Math.floor(ne),
        xe = ne - ce,
        Se = R[ce === 0 ? ce : ce - 1],
        $ = R[ce],
        q = R[ce > R.length - 2 ? R.length - 1 : ce + 1],
        N = R[ce > R.length - 3 ? R.length - 1 : ce + 2];
      return $.mode === 1 || (Se === $ && q.mode === 1)
        ? $.lerp(q, xe, U)
        : U.set(l(g(xe, Se.x, $.x, q.x, N.x)), l(g(xe, Se.y, $.y, q.y, N.y)));
    }
  }
};
