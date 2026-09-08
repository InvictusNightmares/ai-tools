import { defineField as B } from "../fields.js";
// Recovered runtime module; preserve lazy initialization for cyclic dependencies.
export default (t, n, r) => {
  r.d(n, {
    v: () => s,
  });
  class s {
    constructor() {
      B(this, "_events", {});
    }
    clear() {
      return ((this._events = {}), this);
    }
    has(l) {
      return !!this._events[l];
    }
    on(l, g, _, A = !1) {
      let m = this._events[l];
      if (
        (m == null && (m = this._events[l] = []),
        m.findIndex((U) => U.callback === g && (!_ || U.target === _)) > -1)
      ) {
        console.warn(`event: ${l} duplicate registered`);
        return;
      }
      return (
        m.push({
          name: l,
          callback: g,
          target: _,
          once: A,
        }),
        this
      );
    }
    off(l, g, _) {
      let A = this._events[l];
      if (A) {
        let m = A.findIndex((D) => D.callback === g && (!_ || D.target === _));
        this._removeEvent(A, m, l);
      }
      return this;
    }
    onof(l, g, _) {
      return (
        _._listeners === void 0 && (_._listeners = []),
        _._listeners.push({
          name: l,
          callback: g,
        }),
        this.on(l, g),
        this
      );
    }
    offof(l) {
      for (let g of l._listeners) this.off(g.name, g.callback);
      return this;
    }
    _removeEvent(l, g, _) {
      return (g > -1 && (l.splice(g, 1), l.length === 0 && delete this._events[_]), this);
    }
    targetOff(l) {
      for (let g in this._events) {
        let _ = this._events[g];
        for (let A = _.length; A--;) _[A].target === l && this._removeEvent(_, A, g);
      }
    }
    emit(l, ...g) {
      let _ = this._events[l];
      if (_)
        for (let A = _.length; A--;) {
          let m = _[A];
          m &&
            (m.once && this._removeEvent(_, A, l),
            m.target ? m.callback.apply(m.target, g) : m.callback(...g));
        }
      return this;
    }
  }
};
