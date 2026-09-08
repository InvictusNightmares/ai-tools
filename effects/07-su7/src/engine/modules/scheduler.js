import { defineField as B } from "../fields.js";
// Recovered runtime module; preserve lazy initialization for cyclic dependencies.
export default (t, n, r) => {
  r.d(n, {
    b: () => l,
  });
  class s {
    constructor(_, A, m, D) {
      B(this, "_target", null);
      B(this, "_callback", null);
      B(this, "_interval", 0);
      B(this, "_repeat", 0);
      B(this, "_elapsed", 0);
      B(this, "_lastTime", 0);
      B(this, "_repeatForever", !1);
      B(this, "_pause", !1);
      ((this._target = _),
        (this._callback = A),
        (this._interval = m),
        (this._repeat = D),
        (this._repeatForever = D === -1));
    }
    get pause() {
      return this._pause;
    }
    set pause(_) {
      this._pause = _;
    }
    get target() {
      return this._target;
    }
    get callback() {
      return this._callback;
    }
    get lived() {
      return this._repeat > 0 || this._repeatForever;
    }
    update(_) {
      this._pause ||
        ((this._repeat > 0 || this._repeatForever) &&
          ((this._elapsed += _),
          this._elapsed >= this._interval &&
            (this.trigger(this._elapsed - this._lastTime),
            (this._elapsed -= this._interval),
            (this._lastTime = this._elapsed),
            this._repeat--)));
    }
    trigger(_) {
      this._target && this._callback && this._callback.call(this._target, _, this._elapsed);
    }
  }
  class h {
    constructor(_, A) {
      B(this, "_target");
      B(this, "_callers");
      ((this._target = _), (this._callers = A));
    }
    get target() {
      return this._target;
    }
    get callers() {
      return this._callers;
    }
  }
  class l {
    constructor() {
      B(this, "_callers", {});
      B(this, "_callersArray", []);
    }
    pause(_) {
      let A = this._callers[_.uuid];
      A && A.forEach((m) => (m.pause = !0));
    }
    resume(_) {
      let A = this._callers[_.uuid];
      A && A.forEach((m) => (m.pause = !1));
    }
    schedule(_, A, m, D) {
      let U = this._callers[_.uuid];
      (U === void 0 && ((U = this._callers[_.uuid] = []), this._callersArray.push(new h(_, U))),
        U.push(new s(_, A, m, D)));
    }
    unshedule(_, A) {
      let m = this._callers[_.uuid];
      if (m) {
        let D = m.findIndex((U) => U.callback === A);
        D !== -1 && m.splice(D, 1);
      }
    }
    unscheduleAll(_) {
      delete this._callers[_.uuid];
      let A = this._callersArray.findIndex((m) => m.target === _);
      A !== -1 && this._callersArray.splice(A, 1);
    }
    update(_) {
      let A,
        m = this._callersArray;
      for (let D = m.length; D--;) {
        A = m[D].callers;
        for (let U = A.length; U--;) A[U].lived ? A[U].update(_) : A.splice(U, 1);
      }
    }
  }
};
