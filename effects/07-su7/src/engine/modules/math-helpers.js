import { defineField as B } from "../fields.js";
// Recovered runtime module; preserve lazy initialization for cyclic dependencies.
export default (t, n, r) => {
  r.d(n, {
    $c: () => g,
    $p: () => l,
    $q: () => R,
    $r: () => U,
    L0: () => _,
    OE: () => ce,
    bd: () => D,
    eC: () => ne,
    i5: () => A,
    nX: () => m,
    ri: () => xe,
  });
  var s = r(25);
  const { degToRad: h } = s.MathUtils;
  function l(Se, $, q = !1) {
    for (let N in $) {
      let ie = $[N];
      if (ie === void 0) continue;
      let _e = N.split("-"),
        Pe = Se,
        Be = Pe;
      for (let Re = 0, ct = _e.length; Re < ct; Re++) {
        let et = _e[Re];
        if (q || Be.hasOwnProperty(et) || Be.constructor.prototype.hasOwnProperty(et)) {
          if (((Pe = Be[et]), Re == ct - 1)) {
            let Ze = Object.getOwnPropertyDescriptor(Be, et);
            !Ze || Ze.writable || Ze.set ? (Be[et] = ie) : Pe && Pe.copy && Pe.copy(ie);
          }
          Be = Pe;
        }
      }
    }
    return Se;
  }
  function g(...Se) {
    let $ = new s.Ilk();
    return (Se.length === 1 ? $.set(Se[0]) : Se.length === 3 && $.setRGB(Se[0], Se[1], Se[2]), $);
  }
  function _(Se, $, q, N) {
    let ie = new s.Ilk().setHex((Se << 16) + ($ << 8) + q);
    return N !== void 0 ? new s.Ltg(ie.r, ie.g, ie.b, N / 255) : ie;
  }
  function A(Se, $) {
    return new s.FM8(Se, $ ?? Se);
  }
  function m(Se, $, q) {
    return new s.Pa4(Se, $ ?? Se, q ?? Se);
  }
  function D(Se, $, q, N) {
    return new s.Ltg(Se, $ ?? Se, q ?? Se, N ?? Se);
  }
  function U(Se, $, q, N = !1) {
    return N ? new s.USm(h(Se), h($), h(q)) : new s.USm(Se, $, q);
  }
  function R(Se, $, q, N) {
    return new s._fP(Se, $, q, N);
  }
  function ne(Se, $ = new s.Ltg()) {
    return (($.x = Se.r), ($.y = Se.g), ($.z = Se.b), $);
  }
  function ce(Se, $ = new s.Ilk()) {
    return (($.r = Se.x), ($.g = Se.y), ($.b = Se.z), $);
  }
  function xe(Se) {
    return Se != null;
  }
};
