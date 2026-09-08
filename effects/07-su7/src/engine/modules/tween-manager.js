import { defineField as B } from "../fields.js";
// Recovered runtime module; preserve lazy initialization for cyclic dependencies.
export default (t, n, r) => {
  (r.r(n),
    r.d(n, {
      Easing: () => s.Easing,
      Group: () => s.Group,
      Interpolation: () => s.Interpolation,
      Sequence: () => s.Sequence,
      Tween: () => s.Tween,
      TweenChain: () => h.TweenChain,
      TweenManager: () => D,
      VERSION: () => s.VERSION,
      __esModule: () => s.__esModule,
      add: () => s.add,
      getAll: () => s.getAll,
      nextId: () => s.nextId,
      now: () => s.now,
      remove: () => s.remove,
      removeAll: () => s.removeAll,
      update: () => s.update,
    }));
  var s = r(622),
    h = r(631);
  const { Tween: l, getAll: g, remove: _, update: A } = r(622),
    { TweenChain: m } = r(631);
  class D {
    static Tween(R) {
      return new l(R);
    }
    static Timeline(R) {
      return new m(R);
    }
    static KillTweensOf(R) {
      let ne = g();
      for (let ce of ne) ce._object === R && _(ce);
    }
    static TweenUpdate(R) {
      A(R);
    }
  }
};
