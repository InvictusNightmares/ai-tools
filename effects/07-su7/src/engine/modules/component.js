import { defineField as B } from "../fields.js";
// Recovered runtime module; preserve lazy initialization for cyclic dependencies.
export default (t, n, r) => {
  r.d(n, {
    w: () => h,
  });
  var s = r(461);
  class h extends s.Entity {
    constructor() {
      super(...arguments);
      B(this, "_enabled", !0);
      B(this, "node");
      B(this, "viewer");
      B(this, "isComponent", !0);
    }
    get enabled() {
      return this._enabled;
    }
    set enabled(_) {
      var A;
      this._enabled !== _ &&
        ((this._enabled = _),
        (A = this.viewer) == null || A.componentScheduler.enableComponent(this, _));
    }
    _onPreDestroy() {
      var _, A, m;
      (this.unscheduleAll(),
        (_ = this.viewer) == null || _.input.disconnect(this),
        (A = this.viewer) == null || A.removeComponent(this.node, this),
        this._enabled &&
          ((m = this.viewer) == null || m.componentScheduler.enableComponent(this, !1)),
        this.onDestroy && this.__getFlag(s.Entity.Flags.OnLoadCalled) && this.onDestroy());
    }
    schedule(_, A, m = -1) {
      var D;
      (D = this.viewer) == null || D.scheduler.schedule(this, _, A, m);
    }
    unshedule(_) {
      var A;
      (A = this.viewer) == null || A.scheduler.unshedule(this, _);
    }
    unscheduleAll() {
      var _;
      (_ = this.viewer) == null || _.scheduler.unscheduleAll(this);
    }
    on(_, A, m, D) {
      var U;
      return (super.on(_, A, m, D), (U = this.viewer) == null || U.input.connect(this, _), this);
    }
  }
};
