import { defineField as B } from "../fields.js";
// Recovered runtime module; preserve lazy initialization for cyclic dependencies.
export default (t, n, r) => {
  r.d(n, {
    Entity: () => g,
  });
  var s = r(930),
    h;
  (function (_) {
    ((_[(_.Destroyed = 1)] = "Destroyed"),
      (_[(_.OnLoadCalled = 2)] = "OnLoadCalled"),
      (_[(_.OnEnableCalled = 4)] = "OnEnableCalled"),
      (_[(_.StartCalled = 8)] = "StartCalled"),
      (_[(_.Deactivating = 16)] = "Deactivating"),
      (_[(_.IsStartCalled = 32)] = "IsStartCalled"));
  })(h || (h = {}));
  let l = 0;
  class g extends s.v {
    constructor(m) {
      super();
      B(this, "uuid", "" + l++);
      B(this, "name", "");
      B(this, "_objFlags", 0);
      this.name = m || this.name;
    }
    __setFlag(m) {
      this._objFlags |= m;
    }
    __clearFlag(m) {
      this._objFlags &= ~m;
    }
    __getFlag(m) {
      return !!(this._objFlags & m);
    }
    get isValid() {
      return !(this._objFlags & h.Destroyed);
    }
    destroy() {
      return this.__getFlag(h.Destroyed) ? !1 : (this.destroyImmediate(), !0);
    }
    destroyImmediate() {
      (this._onPreDestroy && this._onPreDestroy(), this.__setFlag(h.Destroyed));
    }
  }
  B(g, "Flags", h);
};
