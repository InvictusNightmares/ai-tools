import { defineField as B } from "../fields.js";
// Recovered runtime module; preserve lazy initialization for cyclic dependencies.
export default (t, n, r) => {
  (r.r(n),
    r.d(n, {
      TweenChain: () => h,
    }));
  const s = r(622);
  class h {
    constructor(g) {
      ((this._object = g), (this._tween = new s.Tween(g)));
    }
    start() {
      return (this._tween.start(), this);
    }
    stop() {
      return (this._tween.stop(), this);
    }
    repeat(g) {
      return (this._chainedTween.repeat(g), this);
    }
    union() {
      return (
        (this._chainedTween = this._tween =
          new s.Tween(this._object).union(this._tween, this._chainedTween)),
        this
      );
    }
    call(g) {
      return (this._chainTween().call(g), this);
    }
    delay(g) {
      return (this._chainTween().delay(g), this);
    }
    to(g, _, A) {
      let m = this._chainTween().to(g, _);
      return (
        A &&
          (A.from && m.from(A.from),
          A.easing && m.easing(A.easing),
          A.onStart && m.onStart(A.onStart),
          A.onStop && m.onStop(A.onStop),
          A.onComplete && m.onComplete(A.onComplete),
          A.onUpdate && m.onUpdate(A.onUpdate),
          A.onRepeat && m.onRepeat(A.onRepeat)),
        this
      );
    }
    _chainTween() {
      let g = this._tween;
      return (
        this._chainedTween && ((g = new s.Tween(this._object)), this._chainedTween.chain(g)),
        (this._chainedTween = g),
        g
      );
    }
  }
};
