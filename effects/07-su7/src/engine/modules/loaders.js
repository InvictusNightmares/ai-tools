import { defineField as B } from "../fields.js";
// Recovered runtime module; preserve lazy initialization for cyclic dependencies.
export default (t, n, r) => {
  r.d(n, {
    gO: () => s.g,
    f0: () => g,
    GP: () => A,
    q7: () => pt,
    Ae: () => us,
    uo: () => ye,
    k7: () => Ce,
    KC: () => ni,
    Zt: () => mt,
    YQ: () => nn,
  });
  var s = r(745),
    h = r(811),
    l = r(427);
  class g extends s.g {
    constructor() {
      super(...arguments);
      B(this, "extensions", ["atlas"]);
    }
    load({ url: b, file: E, onLoad: T, onProgress: L, onError: F, texSettings: j }) {
      (async () => {
        try {
          let W = await this.viewer.loadAsset({
              url: b,
              selExt: "json",
            }),
            re = await this.viewer.loadAsset({
              url: `${(0, l.I_)(b)}/${W.meta.image}`,
              onProgress: L,
            });
          T(new h.Y(W, Object.assign(re, j)));
        } catch (W) {
          F(W);
        }
      })();
    }
  }
  var _ = r(25);
  class A extends s.g {
    constructor() {
      super(...arguments);
      B(this, "extensions", ["mp3", "wav", "ogg"]);
    }
    load({ url: b, file: E, onLoad: T, onProgress: L, onError: F }) {
      new _.mTL(this.viewer.loadingManager).load(b, T, L, F, E);
    }
  }
  var m = r(477),
    D = function (ae) {
      return URL.createObjectURL(
        new Blob([ae], {
          type: "text/javascript",
        }),
      );
    };
  try {
    URL.revokeObjectURL(D(""));
  } catch {
    D = function (y) {
      return "data:application/javascript;charset=UTF-8," + encodeURI(y);
    };
  }
  var U = Uint8Array,
    R = Uint16Array,
    ne = Uint32Array,
    ce = new U([
      0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0, 0, 0,
      0,
    ]),
    xe = new U([
      0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13,
      13, 0, 0,
    ]),
    Se = new U([16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15]),
    $ = function (ae, y) {
      for (var b = new R(31), E = 0; E < 31; ++E) b[E] = y += 1 << ae[E - 1];
      for (var T = new ne(b[30]), E = 1; E < 30; ++E)
        for (var L = b[E]; L < b[E + 1]; ++L) T[L] = ((L - b[E]) << 5) | E;
      return [b, T];
    },
    q = $(ce, 2),
    N = q[0],
    ie = q[1];
  ((N[28] = 258), (ie[258] = 28));
  for (var _e = $(xe, 0), Pe = _e[0], Be = new R(32768), Re = 0; Re < 32768; ++Re) {
    var ct = ((Re & 43690) >>> 1) | ((Re & 21845) << 1);
    ((ct = ((ct & 52428) >>> 2) | ((ct & 13107) << 2)),
      (ct = ((ct & 61680) >>> 4) | ((ct & 3855) << 4)),
      (Be[Re] = (((ct & 65280) >>> 8) | ((ct & 255) << 8)) >>> 1));
  }
  for (
    var et = function (ae, y, b) {
        for (var E = ae.length, T = 0, L = new R(y); T < E; ++T) ++L[ae[T] - 1];
        var F = new R(y);
        for (T = 0; T < y; ++T) F[T] = (F[T - 1] + L[T - 1]) << 1;
        var j;
        if (b) {
          j = new R(1 << y);
          var W = 15 - y;
          for (T = 0; T < E; ++T)
            if (ae[T])
              for (
                var re = (T << 4) | ae[T],
                  fe = y - ae[T],
                  te = F[ae[T] - 1]++ << fe,
                  Te = te | ((1 << fe) - 1);
                te <= Te;
                ++te
              )
                j[Be[te] >>> W] = re;
        } else
          for (j = new R(E), T = 0; T < E; ++T)
            ae[T] && (j[T] = Be[F[ae[T] - 1]++] >>> (15 - ae[T]));
        return j;
      },
      Ze = new U(288),
      Re = 0;
    Re < 144;
    ++Re
  )
    Ze[Re] = 8;
  for (var Re = 144; Re < 256; ++Re) Ze[Re] = 9;
  for (var Re = 256; Re < 280; ++Re) Ze[Re] = 7;
  for (var Re = 280; Re < 288; ++Re) Ze[Re] = 8;
  for (var Nt = new U(32), Re = 0; Re < 32; ++Re) Nt[Re] = 5;
  var Bt = et(Ze, 9, 1),
    en = et(Nt, 5, 1),
    li = function (ae) {
      for (var y = ae[0], b = 1; b < ae.length; ++b) ae[b] > y && (y = ae[b]);
      return y;
    },
    di = function (ae, y, b) {
      var E = (y / 8) | 0;
      return ((ae[E] | (ae[E + 1] << 8)) >> (y & 7)) & b;
    },
    xi = function (ae, y) {
      var b = (y / 8) | 0;
      return (ae[b] | (ae[b + 1] << 8) | (ae[b + 2] << 16)) >> (y & 7);
    },
    zt = function (ae) {
      return ((ae / 8) | 0) + (ae & 7 && 1);
    },
    Sn = function (ae, y, b) {
      ((y == null || y < 0) && (y = 0), (b == null || b > ae.length) && (b = ae.length));
      var E = new (ae instanceof R ? R : ae instanceof ne ? ne : U)(b - y);
      return (E.set(ae.subarray(y, b)), E);
    },
    rn = function (ae, y, b) {
      var E = ae.length;
      if (!E || (b && !b.l && E < 5)) return y || new U(0);
      var T = !y || b,
        L = !b || b.i;
      (b || (b = {}), y || (y = new U(E * 3)));
      var F = function (wi) {
          var Mr = y.length;
          if (wi > Mr) {
            var yr = new U(Math.max(Mr * 2, wi));
            (yr.set(y), (y = yr));
          }
        },
        j = b.f || 0,
        W = b.p || 0,
        re = b.b || 0,
        fe = b.l,
        te = b.d,
        Te = b.m,
        Ge = b.n,
        St = E * 8;
      do {
        if (!fe) {
          b.f = j = di(ae, W, 1);
          var kt = di(ae, W + 1, 3);
          if (((W += 3), kt)) {
            if (kt == 1) ((fe = Bt), (te = en), (Te = 9), (Ge = 5));
            else if (kt == 2) {
              var Xe = di(ae, W, 31) + 257,
                ut = di(ae, W + 10, 15) + 4,
                dn = Xe + di(ae, W + 5, 31) + 1;
              W += 14;
              for (var qt = new U(dn), ln = new U(19), Tn = 0; Tn < ut; ++Tn)
                ln[Se[Tn]] = di(ae, W + Tn * 3, 7);
              W += ut * 3;
              for (var fn = li(ln), Hn = (1 << fn) - 1, En = et(ln, fn, 1), Tn = 0; Tn < dn;) {
                var Ei = En[di(ae, W, Hn)];
                W += Ei & 15;
                var Vt = Ei >>> 4;
                if (Vt < 16) qt[Tn++] = Vt;
                else {
                  var ar = 0,
                    fr = 0;
                  for (
                    Vt == 16
                      ? ((fr = 3 + di(ae, W, 3)), (W += 2), (ar = qt[Tn - 1]))
                      : Vt == 17
                        ? ((fr = 3 + di(ae, W, 7)), (W += 3))
                        : Vt == 18 && ((fr = 11 + di(ae, W, 127)), (W += 7));
                    fr--;
                  )
                    qt[Tn++] = ar;
                }
              }
              var lr = qt.subarray(0, Xe),
                is = qt.subarray(Xe);
              ((Te = li(lr)), (Ge = li(is)), (fe = et(lr, Te, 1)), (te = et(is, Ge, 1)));
            } else throw "invalid block type";
          } else {
            var Vt = zt(W) + 4,
              gt = ae[Vt - 4] | (ae[Vt - 3] << 8),
              xt = Vt + gt;
            if (xt > E) {
              if (L) throw "unexpected EOF";
              break;
            }
            (T && F(re + gt), y.set(ae.subarray(Vt, xt), re), (b.b = re += gt), (b.p = W = xt * 8));
            continue;
          }
          if (W > St) {
            if (L) throw "unexpected EOF";
            break;
          }
        }
        T && F(re + 131072);
        for (var Tr = (1 << Te) - 1, Er = (1 << Ge) - 1, Kr = W; ; Kr = W) {
          var ar = fe[xi(ae, W) & Tr],
            Vi = ar >>> 4;
          if (((W += ar & 15), W > St)) {
            if (L) throw "unexpected EOF";
            break;
          }
          if (!ar) throw "invalid length/literal";
          if (Vi < 256) y[re++] = Vi;
          else if (Vi == 256) {
            ((Kr = W), (fe = null));
            break;
          } else {
            var me = Vi - 254;
            if (Vi > 264) {
              var Tn = Vi - 257,
                _r = ce[Tn];
              ((me = di(ae, W, (1 << _r) - 1) + N[Tn]), (W += _r));
            }
            var Qo = te[xi(ae, W) & Er],
              Ji = Qo >>> 4;
            if (!Qo) throw "invalid distance";
            W += Qo & 15;
            var is = Pe[Ji];
            if (Ji > 3) {
              var _r = xe[Ji];
              ((is += xi(ae, W) & ((1 << _r) - 1)), (W += _r));
            }
            if (W > St) {
              if (L) throw "unexpected EOF";
              break;
            }
            T && F(re + 131072);
            for (var xa = re + me; re < xa; re += 4)
              ((y[re] = y[re - is]),
                (y[re + 1] = y[re + 1 - is]),
                (y[re + 2] = y[re + 2 - is]),
                (y[re + 3] = y[re + 3 - is]));
            re = xa;
          }
        }
        ((b.l = fe), (b.p = Kr), (b.b = re), fe && ((j = 1), (b.m = Te), (b.d = te), (b.n = Ge)));
      } while (!j);
      return re == y.length ? y : Sn(y, 0, re);
    },
    Ft = new U(0),
    jt = function (ae) {
      if ((ae[0] & 15) != 8 || ae[0] >>> 4 > 7 || ((ae[0] << 8) | ae[1]) % 31)
        throw "invalid zlib data";
      if (ae[1] & 32) throw "invalid zlib data: preset dictionaries not supported";
    };
  function Xt(ae, y) {
    return rn((jt(ae), ae.subarray(2, -4)), y);
  }
  var Rt = typeof TextDecoder < "u" && new TextDecoder(),
    Wn = 0;
  try {
    (Rt.decode(Ft, {
      stream: !0,
    }),
      (Wn = 1));
  } catch {}
  class He extends m.yxD {
    constructor(y) {
      (super(y), (this.type = m.cLu));
    }
    parse(y) {
      const fn = Math.pow(2.7182818, 2.2);
      function Hn(Y, le) {
        let Ee = 0;
        for (let at = 0; at < 65536; ++at)
          (at == 0 || Y[at >> 3] & (1 << (at & 7))) && (le[Ee++] = at);
        const Ve = Ee - 1;
        for (; Ee < 65536;) le[Ee++] = 0;
        return Ve;
      }
      function En(Y) {
        for (let le = 0; le < 16384; le++)
          ((Y[le] = {}), (Y[le].len = 0), (Y[le].lit = 0), (Y[le].p = null));
      }
      const Ei = {
        l: 0,
        c: 0,
        lc: 0,
      };
      function ar(Y, le, Ee, Ve, at) {
        for (; Ee < Y;) ((le = (le << 8) | Bc(Ve, at)), (Ee += 8));
        ((Ee -= Y), (Ei.l = (le >> Ee) & ((1 << Y) - 1)), (Ei.c = le), (Ei.lc = Ee));
      }
      const fr = new Array(59);
      function lr(Y) {
        for (let Ee = 0; Ee <= 58; ++Ee) fr[Ee] = 0;
        for (let Ee = 0; Ee < 65537; ++Ee) fr[Y[Ee]] += 1;
        let le = 0;
        for (let Ee = 58; Ee > 0; --Ee) {
          const Ve = (le + fr[Ee]) >> 1;
          ((fr[Ee] = le), (le = Ve));
        }
        for (let Ee = 0; Ee < 65537; ++Ee) {
          const Ve = Y[Ee];
          Ve > 0 && (Y[Ee] = Ve | (fr[Ve]++ << 6));
        }
      }
      function is(Y, le, Ee, Ve, at, Qe) {
        const Et = le;
        let Ut = 0,
          Yt = 0;
        for (; Ve <= at; Ve++) {
          if (Et.value - le.value > Ee) return !1;
          ar(6, Ut, Yt, Y, Et);
          const At = Ei.l;
          if (((Ut = Ei.c), (Yt = Ei.lc), (Qe[Ve] = At), At == 63)) {
            if (Et.value - le.value > Ee) throw new Error("Something wrong with hufUnpackEncTable");
            ar(8, Ut, Yt, Y, Et);
            let bt = Ei.l + 6;
            if (((Ut = Ei.c), (Yt = Ei.lc), Ve + bt > at + 1))
              throw new Error("Something wrong with hufUnpackEncTable");
            for (; bt--;) Qe[Ve++] = 0;
            Ve--;
          } else if (At >= 59) {
            let bt = At - 59 + 2;
            if (Ve + bt > at + 1) throw new Error("Something wrong with hufUnpackEncTable");
            for (; bt--;) Qe[Ve++] = 0;
            Ve--;
          }
        }
        lr(Qe);
      }
      function Tr(Y) {
        return Y & 63;
      }
      function Er(Y) {
        return Y >> 6;
      }
      function Kr(Y, le, Ee, Ve) {
        for (; le <= Ee; le++) {
          const at = Er(Y[le]),
            Qe = Tr(Y[le]);
          if (at >> Qe) throw new Error("Invalid table entry");
          if (Qe > 14) {
            const Et = Ve[at >> (Qe - 14)];
            if (Et.len) throw new Error("Invalid table entry");
            if ((Et.lit++, Et.p)) {
              const Ut = Et.p;
              Et.p = new Array(Et.lit);
              for (let Yt = 0; Yt < Et.lit - 1; ++Yt) Et.p[Yt] = Ut[Yt];
            } else Et.p = new Array(1);
            Et.p[Et.lit - 1] = le;
          } else if (Qe) {
            let Et = 0;
            for (let Ut = 1 << (14 - Qe); Ut > 0; Ut--) {
              const Yt = Ve[(at << (14 - Qe)) + Et];
              if (Yt.len || Yt.p) throw new Error("Invalid table entry");
              ((Yt.len = Qe), (Yt.lit = le), Et++);
            }
          }
        }
        return !0;
      }
      const Vi = {
        c: 0,
        lc: 0,
      };
      function me(Y, le, Ee, Ve) {
        ((Y = (Y << 8) | Bc(Ee, Ve)), (le += 8), (Vi.c = Y), (Vi.lc = le));
      }
      const _r = {
        c: 0,
        lc: 0,
      };
      function Qo(Y, le, Ee, Ve, at, Qe, Et, Ut, Yt) {
        if (Y == le) {
          (Ve < 8 && (me(Ee, Ve, at, Qe), (Ee = Vi.c), (Ve = Vi.lc)), (Ve -= 8));
          let At = Ee >> Ve;
          if (((At = new Uint8Array([At])[0]), Ut.value + At > Yt)) return !1;
          const bt = Et[Ut.value - 1];
          for (; At-- > 0;) Et[Ut.value++] = bt;
        } else if (Ut.value < Yt) Et[Ut.value++] = Y;
        else return !1;
        ((_r.c = Ee), (_r.lc = Ve));
      }
      function Ji(Y) {
        return Y & 65535;
      }
      function xa(Y) {
        const le = Ji(Y);
        return le > 32767 ? le - 65536 : le;
      }
      const wi = {
        a: 0,
        b: 0,
      };
      function Mr(Y, le) {
        const Ee = xa(Y),
          at = xa(le),
          Qe = Ee + (at & 1) + (at >> 1),
          Et = Qe,
          Ut = Qe - at;
        ((wi.a = Et), (wi.b = Ut));
      }
      function yr(Y, le) {
        const Ee = Ji(Y),
          Ve = Ji(le),
          at = (Ee - (Ve >> 1)) & 65535,
          Qe = (Ve + at - 32768) & 65535;
        ((wi.a = Qe), (wi.b = at));
      }
      function Wi(Y, le, Ee, Ve, at, Qe, Et) {
        const Ut = Et < 16384,
          Yt = Ee > at ? at : Ee;
        let At = 1,
          bt,
          pn;
        for (; At <= Yt;) At <<= 1;
        for (At >>= 1, bt = At, At >>= 1; At >= 1;) {
          pn = 0;
          const yn = pn + Qe * (at - bt),
            Nn = Qe * At,
            ci = Qe * bt,
            Dn = Ve * At,
            $t = Ve * bt;
          let mn, ki, pr, to;
          for (; pn <= yn; pn += ci) {
            let ir = pn;
            const Bi = pn + Ve * (Ee - bt);
            for (; ir <= Bi; ir += $t) {
              const Hr = ir + Dn,
                Zr = ir + Nn,
                or = Zr + Dn;
              Ut
                ? (Mr(Y[ir + le], Y[Zr + le]),
                  (mn = wi.a),
                  (pr = wi.b),
                  Mr(Y[Hr + le], Y[or + le]),
                  (ki = wi.a),
                  (to = wi.b),
                  Mr(mn, ki),
                  (Y[ir + le] = wi.a),
                  (Y[Hr + le] = wi.b),
                  Mr(pr, to),
                  (Y[Zr + le] = wi.a),
                  (Y[or + le] = wi.b))
                : (yr(Y[ir + le], Y[Zr + le]),
                  (mn = wi.a),
                  (pr = wi.b),
                  yr(Y[Hr + le], Y[or + le]),
                  (ki = wi.a),
                  (to = wi.b),
                  yr(mn, ki),
                  (Y[ir + le] = wi.a),
                  (Y[Hr + le] = wi.b),
                  yr(pr, to),
                  (Y[Zr + le] = wi.a),
                  (Y[or + le] = wi.b));
            }
            if (Ee & At) {
              const Hr = ir + Nn;
              (Ut ? Mr(Y[ir + le], Y[Hr + le]) : yr(Y[ir + le], Y[Hr + le]),
                (mn = wi.a),
                (Y[Hr + le] = wi.b),
                (Y[ir + le] = mn));
            }
          }
          if (at & At) {
            let ir = pn;
            const Bi = pn + Ve * (Ee - bt);
            for (; ir <= Bi; ir += $t) {
              const Hr = ir + Dn;
              (Ut ? Mr(Y[ir + le], Y[Hr + le]) : yr(Y[ir + le], Y[Hr + le]),
                (mn = wi.a),
                (Y[Hr + le] = wi.b),
                (Y[ir + le] = mn));
            }
          }
          ((bt = At), (At >>= 1));
        }
        return pn;
      }
      function Ko(Y, le, Ee, Ve, at, Qe, Et, Ut, Yt) {
        let At = 0,
          bt = 0;
        const pn = Et,
          yn = Math.trunc(Ve.value + (at + 7) / 8);
        for (; Ve.value < yn;)
          for (me(At, bt, Ee, Ve), At = Vi.c, bt = Vi.lc; bt >= 14;) {
            const ci = (At >> (bt - 14)) & 16383,
              Dn = le[ci];
            if (Dn.len)
              ((bt -= Dn.len),
                Qo(Dn.lit, Qe, At, bt, Ee, Ve, Ut, Yt, pn),
                (At = _r.c),
                (bt = _r.lc));
            else {
              if (!Dn.p) throw new Error("hufDecode issues");
              let $t;
              for ($t = 0; $t < Dn.lit; $t++) {
                const mn = Tr(Y[Dn.p[$t]]);
                for (; bt < mn && Ve.value < yn;) (me(At, bt, Ee, Ve), (At = Vi.c), (bt = Vi.lc));
                if (bt >= mn && Er(Y[Dn.p[$t]]) == ((At >> (bt - mn)) & ((1 << mn) - 1))) {
                  ((bt -= mn),
                    Qo(Dn.p[$t], Qe, At, bt, Ee, Ve, Ut, Yt, pn),
                    (At = _r.c),
                    (bt = _r.lc));
                  break;
                }
              }
              if ($t == Dn.lit) throw new Error("hufDecode issues");
            }
          }
        const Nn = (8 - at) & 7;
        for (At >>= Nn, bt -= Nn; bt > 0;) {
          const ci = le[(At << (14 - bt)) & 16383];
          if (ci.len)
            ((bt -= ci.len), Qo(ci.lit, Qe, At, bt, Ee, Ve, Ut, Yt, pn), (At = _r.c), (bt = _r.lc));
          else throw new Error("hufDecode issues");
        }
        return !0;
      }
      function ve(Y, le, Ee, Ve, at, Qe) {
        const Et = {
            value: 0,
          },
          Ut = Ee.value,
          Yt = vi(le, Ee),
          At = vi(le, Ee);
        Ee.value += 4;
        const bt = vi(le, Ee);
        if (((Ee.value += 4), Yt < 0 || Yt >= 65537 || At < 0 || At >= 65537))
          throw new Error("Something wrong with HUF_ENCSIZE");
        const pn = new Array(65537),
          yn = new Array(16384);
        En(yn);
        const Nn = Ve - (Ee.value - Ut);
        if ((is(Y, Ee, Nn, Yt, At, pn), bt > 8 * (Ve - (Ee.value - Ut))))
          throw new Error("Something wrong with hufUncompress");
        (Kr(pn, Yt, At, yn), Ko(pn, yn, Y, Ee, bt, At, Qe, at, Et));
      }
      function oe(Y, le, Ee) {
        for (let Ve = 0; Ve < Ee; ++Ve) le[Ve] = Y[le[Ve]];
      }
      function G(Y) {
        for (let le = 1; le < Y.length; le++) {
          const Ee = Y[le - 1] + Y[le] - 128;
          Y[le] = Ee;
        }
      }
      function ee(Y, le) {
        let Ee = 0,
          Ve = Math.floor((Y.length + 1) / 2),
          at = 0;
        const Qe = Y.length - 1;
        for (; !(at > Qe || ((le[at++] = Y[Ee++]), at > Qe));) le[at++] = Y[Ve++];
      }
      function ke(Y) {
        let le = Y.byteLength;
        const Ee = new Array();
        let Ve = 0;
        const at = new DataView(Y);
        for (; le > 0;) {
          const Qe = at.getInt8(Ve++);
          if (Qe < 0) {
            const Et = -Qe;
            le -= Et + 1;
            for (let Ut = 0; Ut < Et; Ut++) Ee.push(at.getUint8(Ve++));
          } else {
            const Et = Qe;
            le -= 2;
            const Ut = at.getUint8(Ve++);
            for (let Yt = 0; Yt < Et + 1; Yt++) Ee.push(Ut);
          }
        }
        return Ee;
      }
      function Ne(Y, le, Ee, Ve, at, Qe) {
        let Et = new DataView(Qe.buffer);
        const Ut = Ee[Y.idx[0]].width,
          Yt = Ee[Y.idx[0]].height,
          At = 3,
          bt = Math.floor(Ut / 8),
          pn = Math.ceil(Ut / 8),
          yn = Math.ceil(Yt / 8),
          Nn = Ut - (pn - 1) * 8,
          ci = Yt - (yn - 1) * 8,
          Dn = {
            value: 0,
          },
          $t = new Array(At),
          mn = new Array(At),
          ki = new Array(At),
          pr = new Array(At),
          to = new Array(At);
        for (let Bi = 0; Bi < At; ++Bi)
          ((to[Bi] = le[Y.idx[Bi]]),
            ($t[Bi] = Bi < 1 ? 0 : $t[Bi - 1] + pn * yn),
            (mn[Bi] = new Float32Array(64)),
            (ki[Bi] = new Uint16Array(64)),
            (pr[Bi] = new Uint16Array(pn * 64)));
        for (let Bi = 0; Bi < yn; ++Bi) {
          let Hr = 8;
          Bi == yn - 1 && (Hr = ci);
          let Zr = 8;
          for (let Ri = 0; Ri < pn; ++Ri) {
            Ri == pn - 1 && (Zr = Nn);
            for (let er = 0; er < At; ++er)
              (ki[er].fill(0),
                (ki[er][0] = at[$t[er]++]),
                $e(Dn, Ve, ki[er]),
                vt(ki[er], mn[er]),
                Lt(mn[er]));
            Pn(mn);
            for (let er = 0; er < At; ++er) un(mn[er], pr[er], Ri * 64);
          }
          let or = 0;
          for (let Ri = 0; Ri < At; ++Ri) {
            const er = Ee[Y.idx[Ri]].type;
            for (let Hs = 8 * Bi; Hs < 8 * Bi + Hr; ++Hs) {
              or = to[Ri][Hs];
              for (let Zo = 0; Zo < bt; ++Zo) {
                const Ts = Zo * 64 + (Hs & 7) * 8;
                (Et.setUint16(or + 0 * 2 * er, pr[Ri][Ts + 0], !0),
                  Et.setUint16(or + 1 * 2 * er, pr[Ri][Ts + 1], !0),
                  Et.setUint16(or + 2 * 2 * er, pr[Ri][Ts + 2], !0),
                  Et.setUint16(or + 3 * 2 * er, pr[Ri][Ts + 3], !0),
                  Et.setUint16(or + 4 * 2 * er, pr[Ri][Ts + 4], !0),
                  Et.setUint16(or + 5 * 2 * er, pr[Ri][Ts + 5], !0),
                  Et.setUint16(or + 6 * 2 * er, pr[Ri][Ts + 6], !0),
                  Et.setUint16(or + 7 * 2 * er, pr[Ri][Ts + 7], !0),
                  (or += 8 * 2 * er));
              }
            }
            if (bt != pn)
              for (let Hs = 8 * Bi; Hs < 8 * Bi + Hr; ++Hs) {
                const Zo = to[Ri][Hs] + 8 * bt * 2 * er,
                  Ts = bt * 64 + (Hs & 7) * 8;
                for (let Do = 0; Do < Zr; ++Do) Et.setUint16(Zo + Do * 2 * er, pr[Ri][Ts + Do], !0);
              }
          }
        }
        const ir = new Uint16Array(Ut);
        Et = new DataView(Qe.buffer);
        for (let Bi = 0; Bi < At; ++Bi) {
          Ee[Y.idx[Bi]].decoded = !0;
          const Hr = Ee[Y.idx[Bi]].type;
          if (Ee[Bi].type == 2)
            for (let Zr = 0; Zr < Yt; ++Zr) {
              const or = to[Bi][Zr];
              for (let Ri = 0; Ri < Ut; ++Ri) ir[Ri] = Et.getUint16(or + Ri * 2 * Hr, !0);
              for (let Ri = 0; Ri < Ut; ++Ri) Et.setFloat32(or + Ri * 2 * Hr, hn(ir[Ri]), !0);
            }
        }
      }
      function $e(Y, le, Ee) {
        let Ve,
          at = 1;
        for (; at < 64;)
          ((Ve = le[Y.value]),
            Ve == 65280 ? (at = 64) : Ve >> 8 == 255 ? (at += Ve & 255) : ((Ee[at] = Ve), at++),
            Y.value++);
      }
      function vt(Y, le) {
        ((le[0] = hn(Y[0])),
          (le[1] = hn(Y[1])),
          (le[2] = hn(Y[5])),
          (le[3] = hn(Y[6])),
          (le[4] = hn(Y[14])),
          (le[5] = hn(Y[15])),
          (le[6] = hn(Y[27])),
          (le[7] = hn(Y[28])),
          (le[8] = hn(Y[2])),
          (le[9] = hn(Y[4])),
          (le[10] = hn(Y[7])),
          (le[11] = hn(Y[13])),
          (le[12] = hn(Y[16])),
          (le[13] = hn(Y[26])),
          (le[14] = hn(Y[29])),
          (le[15] = hn(Y[42])),
          (le[16] = hn(Y[3])),
          (le[17] = hn(Y[8])),
          (le[18] = hn(Y[12])),
          (le[19] = hn(Y[17])),
          (le[20] = hn(Y[25])),
          (le[21] = hn(Y[30])),
          (le[22] = hn(Y[41])),
          (le[23] = hn(Y[43])),
          (le[24] = hn(Y[9])),
          (le[25] = hn(Y[11])),
          (le[26] = hn(Y[18])),
          (le[27] = hn(Y[24])),
          (le[28] = hn(Y[31])),
          (le[29] = hn(Y[40])),
          (le[30] = hn(Y[44])),
          (le[31] = hn(Y[53])),
          (le[32] = hn(Y[10])),
          (le[33] = hn(Y[19])),
          (le[34] = hn(Y[23])),
          (le[35] = hn(Y[32])),
          (le[36] = hn(Y[39])),
          (le[37] = hn(Y[45])),
          (le[38] = hn(Y[52])),
          (le[39] = hn(Y[54])),
          (le[40] = hn(Y[20])),
          (le[41] = hn(Y[22])),
          (le[42] = hn(Y[33])),
          (le[43] = hn(Y[38])),
          (le[44] = hn(Y[46])),
          (le[45] = hn(Y[51])),
          (le[46] = hn(Y[55])),
          (le[47] = hn(Y[60])),
          (le[48] = hn(Y[21])),
          (le[49] = hn(Y[34])),
          (le[50] = hn(Y[37])),
          (le[51] = hn(Y[47])),
          (le[52] = hn(Y[50])),
          (le[53] = hn(Y[56])),
          (le[54] = hn(Y[59])),
          (le[55] = hn(Y[61])),
          (le[56] = hn(Y[35])),
          (le[57] = hn(Y[36])),
          (le[58] = hn(Y[48])),
          (le[59] = hn(Y[49])),
          (le[60] = hn(Y[57])),
          (le[61] = hn(Y[58])),
          (le[62] = hn(Y[62])),
          (le[63] = hn(Y[63])));
      }
      function Lt(Y) {
        const le = 0.5 * Math.cos(0.7853975),
          Ee = 0.5 * Math.cos(3.14159 / 16),
          Ve = 0.5 * Math.cos(3.14159 / 8),
          at = 0.5 * Math.cos((3 * 3.14159) / 16),
          Qe = 0.5 * Math.cos((5 * 3.14159) / 16),
          Et = 0.5 * Math.cos((3 * 3.14159) / 8),
          Ut = 0.5 * Math.cos((7 * 3.14159) / 16),
          Yt = new Array(4),
          At = new Array(4),
          bt = new Array(4),
          pn = new Array(4);
        for (let yn = 0; yn < 8; ++yn) {
          const Nn = yn * 8;
          ((Yt[0] = Ve * Y[Nn + 2]),
            (Yt[1] = Et * Y[Nn + 2]),
            (Yt[2] = Ve * Y[Nn + 6]),
            (Yt[3] = Et * Y[Nn + 6]),
            (At[0] = Ee * Y[Nn + 1] + at * Y[Nn + 3] + Qe * Y[Nn + 5] + Ut * Y[Nn + 7]),
            (At[1] = at * Y[Nn + 1] - Ut * Y[Nn + 3] - Ee * Y[Nn + 5] - Qe * Y[Nn + 7]),
            (At[2] = Qe * Y[Nn + 1] - Ee * Y[Nn + 3] + Ut * Y[Nn + 5] + at * Y[Nn + 7]),
            (At[3] = Ut * Y[Nn + 1] - Qe * Y[Nn + 3] + at * Y[Nn + 5] - Ee * Y[Nn + 7]),
            (bt[0] = le * (Y[Nn + 0] + Y[Nn + 4])),
            (bt[3] = le * (Y[Nn + 0] - Y[Nn + 4])),
            (bt[1] = Yt[0] + Yt[3]),
            (bt[2] = Yt[1] - Yt[2]),
            (pn[0] = bt[0] + bt[1]),
            (pn[1] = bt[3] + bt[2]),
            (pn[2] = bt[3] - bt[2]),
            (pn[3] = bt[0] - bt[1]),
            (Y[Nn + 0] = pn[0] + At[0]),
            (Y[Nn + 1] = pn[1] + At[1]),
            (Y[Nn + 2] = pn[2] + At[2]),
            (Y[Nn + 3] = pn[3] + At[3]),
            (Y[Nn + 4] = pn[3] - At[3]),
            (Y[Nn + 5] = pn[2] - At[2]),
            (Y[Nn + 6] = pn[1] - At[1]),
            (Y[Nn + 7] = pn[0] - At[0]));
        }
        for (let yn = 0; yn < 8; ++yn)
          ((Yt[0] = Ve * Y[16 + yn]),
            (Yt[1] = Et * Y[16 + yn]),
            (Yt[2] = Ve * Y[48 + yn]),
            (Yt[3] = Et * Y[48 + yn]),
            (At[0] = Ee * Y[8 + yn] + at * Y[24 + yn] + Qe * Y[40 + yn] + Ut * Y[56 + yn]),
            (At[1] = at * Y[8 + yn] - Ut * Y[24 + yn] - Ee * Y[40 + yn] - Qe * Y[56 + yn]),
            (At[2] = Qe * Y[8 + yn] - Ee * Y[24 + yn] + Ut * Y[40 + yn] + at * Y[56 + yn]),
            (At[3] = Ut * Y[8 + yn] - Qe * Y[24 + yn] + at * Y[40 + yn] - Ee * Y[56 + yn]),
            (bt[0] = le * (Y[yn] + Y[32 + yn])),
            (bt[3] = le * (Y[yn] - Y[32 + yn])),
            (bt[1] = Yt[0] + Yt[3]),
            (bt[2] = Yt[1] - Yt[2]),
            (pn[0] = bt[0] + bt[1]),
            (pn[1] = bt[3] + bt[2]),
            (pn[2] = bt[3] - bt[2]),
            (pn[3] = bt[0] - bt[1]),
            (Y[0 + yn] = pn[0] + At[0]),
            (Y[8 + yn] = pn[1] + At[1]),
            (Y[16 + yn] = pn[2] + At[2]),
            (Y[24 + yn] = pn[3] + At[3]),
            (Y[32 + yn] = pn[3] - At[3]),
            (Y[40 + yn] = pn[2] - At[2]),
            (Y[48 + yn] = pn[1] - At[1]),
            (Y[56 + yn] = pn[0] - At[0]));
      }
      function Pn(Y) {
        for (let le = 0; le < 64; ++le) {
          const Ee = Y[0][le],
            Ve = Y[1][le],
            at = Y[2][le];
          ((Y[0][le] = Ee + 1.5747 * at),
            (Y[1][le] = Ee - 0.1873 * Ve - 0.4682 * at),
            (Y[2][le] = Ee + 1.8556 * Ve));
        }
      }
      function un(Y, le, Ee) {
        for (let Ve = 0; Ve < 64; ++Ve) le[Ee + Ve] = m.A5E.toHalfFloat(vn(Y[Ve]));
      }
      function vn(Y) {
        return Y <= 1
          ? Math.sign(Y) * Math.pow(Math.abs(Y), 2.2)
          : Math.sign(Y) * Math.pow(fn, Math.abs(Y) - 1);
      }
      function _n(Y) {
        return new DataView(Y.array.buffer, Y.offset.value, Y.size);
      }
      function qn(Y) {
        const le = Y.viewer.buffer.slice(Y.offset.value, Y.offset.value + Y.size),
          Ee = new Uint8Array(ke(le)),
          Ve = new Uint8Array(Ee.length);
        return (G(Ee), ee(Ee, Ve), new DataView(Ve.buffer));
      }
      function ii(Y) {
        const le = Y.array.slice(Y.offset.value, Y.offset.value + Y.size),
          Ee = Xt(le),
          Ve = new Uint8Array(Ee.length);
        return (G(Ee), ee(Ee, Ve), new DataView(Ve.buffer));
      }
      function Mi(Y) {
        const le = Y.viewer,
          Ee = {
            value: Y.offset.value,
          },
          Ve = new Uint16Array(Y.width * Y.scanlineBlockSize * (Y.channels * Y.type)),
          at = new Uint8Array(8192);
        let Qe = 0;
        const Et = new Array(Y.channels);
        for (let ci = 0; ci < Y.channels; ci++)
          ((Et[ci] = {}),
            (Et[ci].start = Qe),
            (Et[ci].end = Et[ci].start),
            (Et[ci].nx = Y.width),
            (Et[ci].ny = Y.lines),
            (Et[ci].size = Y.type),
            (Qe += Et[ci].nx * Et[ci].ny * Et[ci].size));
        const Ut = Fc(le, Ee),
          Yt = Fc(le, Ee);
        if (Yt >= 8192) throw new Error("Something is wrong with PIZ_COMPRESSION BITMAP_SIZE");
        if (Ut <= Yt) for (let ci = 0; ci < Yt - Ut + 1; ci++) at[ci + Ut] = Ro(le, Ee);
        const At = new Uint16Array(65536),
          bt = Hn(at, At),
          pn = vi(le, Ee);
        ve(Y.array, le, Ee, pn, Ve, Qe);
        for (let ci = 0; ci < Y.channels; ++ci) {
          const Dn = Et[ci];
          for (let $t = 0; $t < Et[ci].size; ++$t)
            Wi(Ve, Dn.start + $t, Dn.nx, Dn.size, Dn.ny, Dn.nx * Dn.size, bt);
        }
        oe(At, Ve, Qe);
        let yn = 0;
        const Nn = new Uint8Array(Ve.buffer.byteLength);
        for (let ci = 0; ci < Y.lines; ci++)
          for (let Dn = 0; Dn < Y.channels; Dn++) {
            const $t = Et[Dn],
              mn = $t.nx * $t.size,
              ki = new Uint8Array(Ve.buffer, $t.end * 2, mn * 2);
            (Nn.set(ki, yn), (yn += mn * 2), ($t.end += mn));
          }
        return new DataView(Nn.buffer);
      }
      function Jn(Y) {
        const le = Y.array.slice(Y.offset.value, Y.offset.value + Y.size),
          Ee = Xt(le),
          Ve = Y.lines * Y.channels * Y.width,
          at = Y.type == 1 ? new Uint16Array(Ve) : new Uint32Array(Ve);
        let Qe = 0,
          Et = 0;
        const Ut = new Array(4);
        for (let Yt = 0; Yt < Y.lines; Yt++)
          for (let At = 0; At < Y.channels; At++) {
            let bt = 0;
            switch (Y.type) {
              case 1:
                ((Ut[0] = Qe), (Ut[1] = Ut[0] + Y.width), (Qe = Ut[1] + Y.width));
                for (let pn = 0; pn < Y.width; ++pn) {
                  const yn = (Ee[Ut[0]++] << 8) | Ee[Ut[1]++];
                  ((bt += yn), (at[Et] = bt), Et++);
                }
                break;
              case 2:
                ((Ut[0] = Qe),
                  (Ut[1] = Ut[0] + Y.width),
                  (Ut[2] = Ut[1] + Y.width),
                  (Qe = Ut[2] + Y.width));
                for (let pn = 0; pn < Y.width; ++pn) {
                  const yn = (Ee[Ut[0]++] << 24) | (Ee[Ut[1]++] << 16) | (Ee[Ut[2]++] << 8);
                  ((bt += yn), (at[Et] = bt), Et++);
                }
                break;
            }
          }
        return new DataView(at.buffer);
      }
      function cr(Y) {
        const le = Y.viewer,
          Ee = {
            value: Y.offset.value,
          },
          Ve = new Uint8Array(Y.width * Y.lines * (Y.channels * Y.type * 2)),
          at = {
            version: Ss(le, Ee),
            unknownUncompressedSize: Ss(le, Ee),
            unknownCompressedSize: Ss(le, Ee),
            acCompressedSize: Ss(le, Ee),
            dcCompressedSize: Ss(le, Ee),
            rleCompressedSize: Ss(le, Ee),
            rleUncompressedSize: Ss(le, Ee),
            rleRawSize: Ss(le, Ee),
            totalAcUncompressedCount: Ss(le, Ee),
            totalDcUncompressedCount: Ss(le, Ee),
            acCompression: Ss(le, Ee),
          };
        if (at.version < 2)
          throw new Error(
            "EXRLoader.parse: " + gl.compression + " version " + at.version + " is unsupported",
          );
        const Qe = new Array();
        let Et = Fc(le, Ee) - 2;
        for (; Et > 0;) {
          const Dn = ur(le.buffer, Ee),
            $t = Ro(le, Ee),
            mn = ($t >> 2) & 3,
            ki = ($t >> 4) - 1,
            pr = new Int8Array([ki])[0],
            to = Ro(le, Ee);
          (Qe.push({
            name: Dn,
            index: pr,
            type: to,
            compression: mn,
          }),
            (Et -= Dn.length + 3));
        }
        const Ut = gl.channels,
          Yt = new Array(Y.channels);
        for (let Dn = 0; Dn < Y.channels; ++Dn) {
          const $t = (Yt[Dn] = {}),
            mn = Ut[Dn];
          (($t.name = mn.name),
            ($t.compression = 0),
            ($t.decoded = !1),
            ($t.type = mn.pixelType),
            ($t.pLinear = mn.pLinear),
            ($t.width = Y.width),
            ($t.height = Y.lines));
        }
        const At = {
          idx: new Array(3),
        };
        for (let Dn = 0; Dn < Y.channels; ++Dn) {
          const $t = Yt[Dn];
          for (let mn = 0; mn < Qe.length; ++mn) {
            const ki = Qe[mn];
            $t.name == ki.name &&
              (($t.compression = ki.compression),
              ki.index >= 0 && (At.idx[ki.index] = Dn),
              ($t.offset = Dn));
          }
        }
        let bt, pn, yn;
        if (at.acCompressedSize > 0)
          switch (at.acCompression) {
            case 0:
              ((bt = new Uint16Array(at.totalAcUncompressedCount)),
                ve(Y.array, le, Ee, at.acCompressedSize, bt, at.totalAcUncompressedCount));
              break;
            case 1:
              const Dn = Y.array.slice(Ee.value, Ee.value + at.totalAcUncompressedCount),
                $t = Xt(Dn);
              ((bt = new Uint16Array($t.buffer)), (Ee.value += at.totalAcUncompressedCount));
              break;
          }
        if (at.dcCompressedSize > 0) {
          const Dn = {
            array: Y.array,
            offset: Ee,
            size: at.dcCompressedSize,
          };
          ((pn = new Uint16Array(ii(Dn).buffer)), (Ee.value += at.dcCompressedSize));
        }
        if (at.rleRawSize > 0) {
          const Dn = Y.array.slice(Ee.value, Ee.value + at.rleCompressedSize),
            $t = Xt(Dn);
          ((yn = ke($t.buffer)), (Ee.value += at.rleCompressedSize));
        }
        let Nn = 0;
        const ci = new Array(Yt.length);
        for (let Dn = 0; Dn < ci.length; ++Dn) ci[Dn] = new Array();
        for (let Dn = 0; Dn < Y.lines; ++Dn)
          for (let $t = 0; $t < Yt.length; ++$t)
            (ci[$t].push(Nn), (Nn += Yt[$t].width * Y.type * 2));
        Ne(At, ci, Yt, bt, pn, Ve);
        for (let Dn = 0; Dn < Yt.length; ++Dn) {
          const $t = Yt[Dn];
          if (!$t.decoded)
            switch ($t.compression) {
              case 2:
                let mn = 0,
                  ki = 0;
                for (let pr = 0; pr < Y.lines; ++pr) {
                  let to = ci[Dn][mn];
                  for (let ir = 0; ir < $t.width; ++ir) {
                    for (let Bi = 0; Bi < 2 * $t.type; ++Bi)
                      Ve[to++] = yn[ki + Bi * $t.width * $t.height];
                    ki++;
                  }
                  mn++;
                }
                break;
              case 1:
              default:
                throw new Error("EXRLoader.parse: unsupported channel compression");
            }
        }
        return new DataView(Ve.buffer);
      }
      function ur(Y, le) {
        const Ee = new Uint8Array(Y);
        let Ve = 0;
        for (; Ee[le.value + Ve] != 0;) Ve += 1;
        const at = new TextDecoder().decode(Ee.slice(le.value, le.value + Ve));
        return ((le.value = le.value + Ve + 1), at);
      }
      function fi(Y, le, Ee) {
        const Ve = new TextDecoder().decode(new Uint8Array(Y).slice(le.value, le.value + Ee));
        return ((le.value = le.value + Ee), Ve);
      }
      function As(Y, le) {
        const Ee = hr(Y, le),
          Ve = vi(Y, le);
        return [Ee, Ve];
      }
      function kr(Y, le) {
        const Ee = vi(Y, le),
          Ve = vi(Y, le);
        return [Ee, Ve];
      }
      function hr(Y, le) {
        const Ee = Y.getInt32(le.value, !0);
        return ((le.value = le.value + 4), Ee);
      }
      function vi(Y, le) {
        const Ee = Y.getUint32(le.value, !0);
        return ((le.value = le.value + 4), Ee);
      }
      function Bc(Y, le) {
        const Ee = Y[le.value];
        return ((le.value = le.value + 1), Ee);
      }
      function Ro(Y, le) {
        const Ee = Y.getUint8(le.value);
        return ((le.value = le.value + 1), Ee);
      }
      const Ss = function (Y, le) {
        let Ee;
        return (
          "getBigInt64" in DataView.prototype
            ? (Ee = Number(Y.getBigInt64(le.value, !0)))
            : (Ee = Y.getUint32(le.value + 4, !0) + Number(Y.getUint32(le.value, !0) << 32)),
          (le.value += 8),
          Ee
        );
      };
      function xr(Y, le) {
        const Ee = Y.getFloat32(le.value, !0);
        return ((le.value += 4), Ee);
      }
      function ml(Y, le) {
        return m.A5E.toHalfFloat(xr(Y, le));
      }
      function hn(Y) {
        const le = (Y & 31744) >> 10,
          Ee = Y & 1023;
        return (
          (Y >> 15 ? -1 : 1) *
          (le
            ? le === 31
              ? Ee
                ? NaN
                : 1 / 0
              : Math.pow(2, le - 15) * (1 + Ee / 1024)
            : 6103515625e-14 * (Ee / 1024))
        );
      }
      function Fc(Y, le) {
        const Ee = Y.getUint16(le.value, !0);
        return ((le.value += 2), Ee);
      }
      function Dg(Y, le) {
        return hn(Fc(Y, le));
      }
      function Lg(Y, le, Ee, Ve) {
        const at = Ee.value,
          Qe = [];
        for (; Ee.value < at + Ve - 1;) {
          const Et = ur(le, Ee),
            Ut = hr(Y, Ee),
            Yt = Ro(Y, Ee);
          Ee.value += 3;
          const At = hr(Y, Ee),
            bt = hr(Y, Ee);
          Qe.push({
            name: Et,
            pixelType: Ut,
            pLinear: Yt,
            xSampling: At,
            ySampling: bt,
          });
        }
        return ((Ee.value += 1), Qe);
      }
      function Uf(Y, le) {
        const Ee = xr(Y, le),
          Ve = xr(Y, le),
          at = xr(Y, le),
          Qe = xr(Y, le),
          Et = xr(Y, le),
          Ut = xr(Y, le),
          Yt = xr(Y, le),
          At = xr(Y, le);
        return {
          redX: Ee,
          redY: Ve,
          greenX: at,
          greenY: Qe,
          blueX: Et,
          blueY: Ut,
          whiteX: Yt,
          whiteY: At,
        };
      }
      function Ig(Y, le) {
        const Ee = [
            "NO_COMPRESSION",
            "RLE_COMPRESSION",
            "ZIPS_COMPRESSION",
            "ZIP_COMPRESSION",
            "PIZ_COMPRESSION",
            "PXR24_COMPRESSION",
            "B44_COMPRESSION",
            "B44A_COMPRESSION",
            "DWAA_COMPRESSION",
            "DWAB_COMPRESSION",
          ],
          Ve = Ro(Y, le);
        return Ee[Ve];
      }
      function Og(Y, le) {
        const Ee = vi(Y, le),
          Ve = vi(Y, le),
          at = vi(Y, le),
          Qe = vi(Y, le);
        return {
          xMin: Ee,
          yMin: Ve,
          xMax: at,
          yMax: Qe,
        };
      }
      function zh(Y, le) {
        const Ee = ["INCREASING_Y"],
          Ve = Ro(Y, le);
        return Ee[Ve];
      }
      function Nf(Y, le) {
        const Ee = xr(Y, le),
          Ve = xr(Y, le);
        return [Ee, Ve];
      }
      function Bg(Y, le) {
        const Ee = xr(Y, le),
          Ve = xr(Y, le),
          at = xr(Y, le);
        return [Ee, Ve, at];
      }
      function Fg(Y, le, Ee, Ve, at) {
        if (Ve === "string" || Ve === "stringvector" || Ve === "iccProfile") return fi(le, Ee, at);
        if (Ve === "chlist") return Lg(Y, le, Ee, at);
        if (Ve === "chromaticities") return Uf(Y, Ee);
        if (Ve === "compression") return Ig(Y, Ee);
        if (Ve === "box2i") return Og(Y, Ee);
        if (Ve === "lineOrder") return zh(Y, Ee);
        if (Ve === "float") return xr(Y, Ee);
        if (Ve === "v2f") return Nf(Y, Ee);
        if (Ve === "v3f") return Bg(Y, Ee);
        if (Ve === "int") return hr(Y, Ee);
        if (Ve === "rational") return As(Y, Ee);
        if (Ve === "timecode") return kr(Y, Ee);
        if (Ve === "preview") return ((Ee.value += at), "skipped");
        Ee.value += at;
      }
      function kg(Y, le, Ee) {
        const Ve = {};
        if (Y.getUint32(0, !0) != 20000630)
          throw new Error("THREE.EXRLoader: provided file doesn't appear to be in OpenEXR format.");
        Ve.version = Y.getUint8(4);
        const at = Y.getUint8(5);
        ((Ve.spec = {
          singleTile: !!(at & 2),
          longName: !!(at & 4),
          deepFormat: !!(at & 8),
          multiPart: !!(at & 16),
        }),
          (Ee.value = 8));
        let Qe = !0;
        for (; Qe;) {
          const Et = ur(le, Ee);
          if (Et == 0) Qe = !1;
          else {
            const Ut = ur(le, Ee),
              Yt = vi(Y, Ee),
              At = Fg(Y, le, Ee, Ut, Yt);
            At === void 0
              ? console.warn(`EXRLoader.parse: skipped unknown header attribute type '${Ut}'.`)
              : (Ve[Et] = At);
          }
        }
        if (at & -5)
          throw (
            console.error("EXRHeader:", Ve),
            new Error("THREE.EXRLoader: provided file is currently unsupported.")
          );
        return Ve;
      }
      function Ug(Y, le, Ee, Ve, at) {
        const Qe = {
          size: 0,
          viewer: le,
          array: Ee,
          offset: Ve,
          width: Y.dataWindow.xMax - Y.dataWindow.xMin + 1,
          height: Y.dataWindow.yMax - Y.dataWindow.yMin + 1,
          channels: Y.channels.length,
          bytesPerLine: null,
          lines: null,
          inputSize: null,
          type: Y.channels[0].pixelType,
          uncompress: null,
          getter: null,
          format: null,
          encoding: null,
        };
        switch (Y.compression) {
          case "NO_COMPRESSION":
            ((Qe.lines = 1), (Qe.uncompress = _n));
            break;
          case "RLE_COMPRESSION":
            ((Qe.lines = 1), (Qe.uncompress = qn));
            break;
          case "ZIPS_COMPRESSION":
            ((Qe.lines = 1), (Qe.uncompress = ii));
            break;
          case "ZIP_COMPRESSION":
            ((Qe.lines = 16), (Qe.uncompress = ii));
            break;
          case "PIZ_COMPRESSION":
            ((Qe.lines = 32), (Qe.uncompress = Mi));
            break;
          case "PXR24_COMPRESSION":
            ((Qe.lines = 16), (Qe.uncompress = Jn));
            break;
          case "DWAA_COMPRESSION":
            ((Qe.lines = 32), (Qe.uncompress = cr));
            break;
          case "DWAB_COMPRESSION":
            ((Qe.lines = 256), (Qe.uncompress = cr));
            break;
          default:
            throw new Error("EXRLoader.parse: " + Y.compression + " is unsupported");
        }
        if (((Qe.scanlineBlockSize = Qe.lines), Qe.type == 1))
          switch (at) {
            case m.VzW:
              ((Qe.getter = Dg), (Qe.inputSize = 2));
              break;
            case m.cLu:
              ((Qe.getter = Fc), (Qe.inputSize = 2));
              break;
          }
        else if (Qe.type == 2)
          switch (at) {
            case m.VzW:
              ((Qe.getter = xr), (Qe.inputSize = 4));
              break;
            case m.cLu:
              ((Qe.getter = ml), (Qe.inputSize = 4));
          }
        else
          throw new Error(
            "EXRLoader.parse: unsupported pixelType " + Qe.type + " for " + Y.compression + ".",
          );
        Qe.blockCount = (Y.dataWindow.yMax + 1) / Qe.scanlineBlockSize;
        for (let Ut = 0; Ut < Qe.blockCount; Ut++) Ss(le, Ve);
        Qe.outputChannels = Qe.channels == 3 ? 4 : Qe.channels;
        const Et = Qe.width * Qe.height * Qe.outputChannels;
        switch (at) {
          case m.VzW:
            ((Qe.byteArray = new Float32Array(Et)),
              Qe.channels < Qe.outputChannels && Qe.byteArray.fill(1, 0, Et));
            break;
          case m.cLu:
            ((Qe.byteArray = new Uint16Array(Et)),
              Qe.channels < Qe.outputChannels && Qe.byteArray.fill(15360, 0, Et));
            break;
          default:
            console.error("THREE.EXRLoader: unsupported type: ", at);
            break;
        }
        return (
          (Qe.bytesPerLine = Qe.width * Qe.inputSize * Qe.channels),
          Qe.outputChannels == 4
            ? ((Qe.format = m.wk1), (Qe.encoding = m.rnI))
            : ((Qe.format = m.hEm), (Qe.encoding = m.rnI)),
          Qe
        );
      }
      const Tu = new DataView(y),
        _t = new Uint8Array(y),
        Cr = {
          value: 0,
        },
        gl = kg(Tu, y, Cr),
        Ci = Ug(gl, Tu, _t, Cr, this.type),
        zf = {
          value: 0,
        },
        Yl = {
          R: 0,
          G: 1,
          B: 2,
          A: 3,
          Y: 0,
        };
      for (let Y = 0; Y < Ci.height / Ci.scanlineBlockSize; Y++) {
        const le = vi(Tu, Cr);
        ((Ci.size = vi(Tu, Cr)),
          (Ci.lines =
            le + Ci.scanlineBlockSize > Ci.height ? Ci.height - le : Ci.scanlineBlockSize));
        const Ve = Ci.size < Ci.lines * Ci.bytesPerLine ? Ci.uncompress(Ci) : _n(Ci);
        Cr.value += Ci.size;
        for (let at = 0; at < Ci.scanlineBlockSize; at++) {
          const Qe = at + Y * Ci.scanlineBlockSize;
          if (Qe >= Ci.height) break;
          for (let Et = 0; Et < Ci.channels; Et++) {
            const Ut = Yl[gl.channels[Et].name];
            for (let Yt = 0; Yt < Ci.width; Yt++) {
              zf.value = (at * (Ci.channels * Ci.width) + Et * Ci.width + Yt) * Ci.inputSize;
              const At =
                (Ci.height - 1 - Qe) * (Ci.width * Ci.outputChannels) + Yt * Ci.outputChannels + Ut;
              Ci.byteArray[At] = Ci.getter(Ve, zf);
            }
          }
        }
      }
      return {
        header: gl,
        width: Ci.width,
        height: Ci.height,
        data: Ci.byteArray,
        format: Ci.format,
        encoding: Ci.encoding,
        type: this.type,
      };
    }
    setDataType(y) {
      return ((this.type = y), this);
    }
    load(y, b, E, T) {
      function L(F, j) {
        ((F.encoding = j.encoding),
          (F.minFilter = m.wem),
          (F.magFilter = m.wem),
          (F.generateMipmaps = !1),
          (F.flipY = !1),
          b && b(F, j));
      }
      return super.load(y, L, E, T);
    }
  }
  class pt extends s.g {
    constructor() {
      super(...arguments);
      B(this, "extensions", ["exr"]);
    }
    load({ url: b, file: E, onLoad: T, onProgress: L, onError: F, texSettings: j }) {
      new He(this.viewer.loadingManager).load(b, (W) => T(Object.assign(W, j)), L, F, E);
    }
  }
  function Fe(ae, y, b) {
    const E = b.length - ae - 1;
    if (y >= b[E]) return E - 1;
    if (y <= b[ae]) return ae;
    let T = ae,
      L = E,
      F = Math.floor((T + L) / 2);
    for (; y < b[F] || y >= b[F + 1];)
      (y < b[F] ? (L = F) : (T = F), (F = Math.floor((T + L) / 2)));
    return F;
  }
  function qe(ae, y, b, E) {
    const T = [],
      L = [],
      F = [];
    T[0] = 1;
    for (let j = 1; j <= b; ++j) {
      ((L[j] = y - E[ae + 1 - j]), (F[j] = E[ae + j] - y));
      let W = 0;
      for (let re = 0; re < j; ++re) {
        const fe = F[re + 1],
          te = L[j - re],
          Te = T[re] / (fe + te);
        ((T[re] = W + fe * Te), (W = te * Te));
      }
      T[j] = W;
    }
    return T;
  }
  function wt(ae, y, b, E) {
    const T = Fe(ae, E, y),
      L = qe(T, E, ae, y),
      F = new m.Ltg(0, 0, 0, 0);
    for (let j = 0; j <= ae; ++j) {
      const W = b[T - ae + j],
        re = L[j],
        fe = W.w * re;
      ((F.x += W.x * fe), (F.y += W.y * fe), (F.z += W.z * fe), (F.w += W.w * re));
    }
    return F;
  }
  function An(ae, y, b, E, T) {
    const L = [];
    for (let te = 0; te <= b; ++te) L[te] = 0;
    const F = [];
    for (let te = 0; te <= E; ++te) F[te] = L.slice(0);
    const j = [];
    for (let te = 0; te <= b; ++te) j[te] = L.slice(0);
    j[0][0] = 1;
    const W = L.slice(0),
      re = L.slice(0);
    for (let te = 1; te <= b; ++te) {
      ((W[te] = y - T[ae + 1 - te]), (re[te] = T[ae + te] - y));
      let Te = 0;
      for (let Ge = 0; Ge < te; ++Ge) {
        const St = re[Ge + 1],
          kt = W[te - Ge];
        j[te][Ge] = St + kt;
        const Vt = j[Ge][te - 1] / j[te][Ge];
        ((j[Ge][te] = Te + St * Vt), (Te = kt * Vt));
      }
      j[te][te] = Te;
    }
    for (let te = 0; te <= b; ++te) F[0][te] = j[te][b];
    for (let te = 0; te <= b; ++te) {
      let Te = 0,
        Ge = 1;
      const St = [];
      for (let kt = 0; kt <= b; ++kt) St[kt] = L.slice(0);
      St[0][0] = 1;
      for (let kt = 1; kt <= E; ++kt) {
        let Vt = 0;
        const gt = te - kt,
          xt = b - kt;
        te >= kt && ((St[Ge][0] = St[Te][0] / j[xt + 1][gt]), (Vt = St[Ge][0] * j[gt][xt]));
        const Xe = gt >= -1 ? 1 : -gt,
          ut = te - 1 <= xt ? kt - 1 : b - te;
        for (let qt = Xe; qt <= ut; ++qt)
          ((St[Ge][qt] = (St[Te][qt] - St[Te][qt - 1]) / j[xt + 1][gt + qt]),
            (Vt += St[Ge][qt] * j[gt + qt][xt]));
        (te <= xt &&
          ((St[Ge][kt] = -St[Te][kt - 1] / j[xt + 1][te]), (Vt += St[Ge][kt] * j[te][xt])),
          (F[kt][te] = Vt));
        const dn = Te;
        ((Te = Ge), (Ge = dn));
      }
    }
    let fe = b;
    for (let te = 1; te <= E; ++te) {
      for (let Te = 0; Te <= b; ++Te) F[te][Te] *= fe;
      fe *= b - te;
    }
    return F;
  }
  function Qt(ae, y, b, E, T) {
    const L = T < ae ? T : ae,
      F = [],
      j = Fe(ae, E, y),
      W = An(j, E, ae, L, y),
      re = [];
    for (let fe = 0; fe < b.length; ++fe) {
      const te = b[fe].clone(),
        Te = te.w;
      ((te.x *= Te), (te.y *= Te), (te.z *= Te), (re[fe] = te));
    }
    for (let fe = 0; fe <= L; ++fe) {
      const te = re[j - ae].clone().multiplyScalar(W[fe][0]);
      for (let Te = 1; Te <= ae; ++Te) te.add(re[j - ae + Te].clone().multiplyScalar(W[fe][Te]));
      F[fe] = te;
    }
    for (let fe = L + 1; fe <= T + 1; ++fe) F[fe] = new m.Ltg(0, 0, 0);
    return F;
  }
  function Pi(ae, y) {
    let b = 1;
    for (let T = 2; T <= ae; ++T) b *= T;
    let E = 1;
    for (let T = 2; T <= y; ++T) E *= T;
    for (let T = 2; T <= ae - y; ++T) E *= T;
    return b / E;
  }
  function ui(ae) {
    const y = ae.length,
      b = [],
      E = [];
    for (let L = 0; L < y; ++L) {
      const F = ae[L];
      ((b[L] = new m.Pa4(F.x, F.y, F.z)), (E[L] = F.w));
    }
    const T = [];
    for (let L = 0; L < y; ++L) {
      const F = b[L].clone();
      for (let j = 1; j <= L; ++j) F.sub(T[L - j].clone().multiplyScalar(Pi(L, j) * E[j]));
      T[L] = F.divideScalar(E[0]);
    }
    return T;
  }
  function mi(ae, y, b, E, T) {
    const L = Qt(ae, y, b, E, T);
    return ui(L);
  }
  class Si extends m.Hyl {
    constructor(y, b, E, T, L) {
      (super(),
        (this.degree = y),
        (this.knots = b),
        (this.controlPoints = []),
        (this.startKnot = T || 0),
        (this.endKnot = L || this.knots.length - 1));
      for (let F = 0; F < E.length; ++F) {
        const j = E[F];
        this.controlPoints[F] = new m.Ltg(j.x, j.y, j.z, j.w);
      }
    }
    getPoint(y, b = new m.Pa4()) {
      const E = b,
        T =
          this.knots[this.startKnot] + y * (this.knots[this.endKnot] - this.knots[this.startKnot]),
        L = wt(this.degree, this.knots, this.controlPoints, T);
      return (L.w !== 1 && L.divideScalar(L.w), E.set(L.x, L.y, L.z));
    }
    getTangent(y, b = new m.Pa4()) {
      const E = b,
        T = this.knots[0] + y * (this.knots[this.knots.length - 1] - this.knots[0]),
        L = mi(this.degree, this.knots, this.controlPoints, T, 1);
      return (E.copy(L[1]).normalize(), E);
    }
  }
  let Gt, On, kn;
  class bi extends m.aNw {
    constructor(y) {
      super(y);
    }
    load(y, b, E, T, L) {
      const F = this,
        j = F.path === "" ? m.Zp0.extractUrlBase(y) : F.path,
        W = new m.hH6(this.manager);
      (W.setPath(F.path),
        W.setResponseType("arraybuffer"),
        W.setRequestHeader(F.requestHeader),
        W.setWithCredentials(F.withCredentials),
        W.load(
          y,
          function (re) {
            try {
              b(F.parse(re, j));
            } catch (fe) {
              (T ? T(fe) : console.error(fe), F.manager.itemError(y));
            }
          },
          E,
          T,
          L == null ? void 0 : L.mainFile,
        ));
    }
    parse(y, b) {
      if (ys(y)) Gt = new Oi().parse(y);
      else {
        const T = Ba(y);
        if (!xs(T)) throw new Error("THREE.FBXLoader: Unknown format.");
        if (hi(T) < 7e3)
          throw new Error("THREE.FBXLoader: FBX version not supported, FileVersion: " + hi(T));
        Gt = new vr().parse(T);
      }
      const E = new m.dpR(this.manager)
        .setPath(this.resourcePath || b)
        .setCrossOrigin(this.crossOrigin);
      return new $i(E, this.manager).parse(Gt);
    }
  }
  class $i {
    constructor(y, b) {
      ((this.textureLoader = y), (this.manager = b));
    }
    parse() {
      On = this.parseConnections();
      const y = this.parseImages(),
        b = this.parseTextures(y),
        E = this.parseMaterials(b),
        T = this.parseDeformers(),
        L = new zr().parse(T);
      return (this.parseScene(T, L, E), kn);
    }
    parseConnections() {
      const y = new Map();
      return (
        "Connections" in Gt &&
          Gt.Connections.connections.forEach(function (E) {
            const T = E[0],
              L = E[1],
              F = E[2];
            y.has(T) ||
              y.set(T, {
                parents: [],
                children: [],
              });
            const j = {
              ID: L,
              relationship: F,
            };
            (y.get(T).parents.push(j),
              y.has(L) ||
                y.set(L, {
                  parents: [],
                  children: [],
                }));
            const W = {
              ID: T,
              relationship: F,
            };
            y.get(L).children.push(W);
          }),
        y
      );
    }
    parseImages() {
      const y = {},
        b = {};
      if ("Video" in Gt.Objects) {
        const E = Gt.Objects.Video;
        for (const T in E) {
          const L = E[T],
            F = parseInt(T);
          if (((y[F] = L.RelativeFilename || L.Filename), "Content" in L)) {
            const j = L.Content instanceof ArrayBuffer && L.Content.byteLength > 0,
              W = typeof L.Content == "string" && L.Content !== "";
            if (j || W) {
              const re = this.parseImage(E[T]);
              b[L.RelativeFilename || L.Filename] = re;
            }
          }
        }
      }
      for (const E in y) {
        const T = y[E];
        b[T] !== void 0 ? (y[E] = b[T]) : (y[E] = y[E].split("\\").pop());
      }
      return y;
    }
    parseImage(y) {
      const b = y.Content,
        E = y.RelativeFilename || y.Filename,
        T = E.slice(E.lastIndexOf(".") + 1).toLowerCase();
      let L;
      switch (T) {
        case "bmp":
          L = "image/bmp";
          break;
        case "jpg":
        case "jpeg":
          L = "image/jpeg";
          break;
        case "png":
          L = "image/png";
          break;
        case "tif":
          L = "image/tiff";
          break;
        case "tga":
          (this.manager.getHandler(".tga") === null &&
            console.warn("FBXLoader: TGA loader not found, skipping ", E),
            (L = "image/tga"));
          break;
        default:
          console.warn('FBXLoader: Image type "' + T + '" is not supported.');
          return;
      }
      if (typeof b == "string") return "data:" + L + ";base64," + b;
      {
        const F = new Uint8Array(b);
        return window.URL.createObjectURL(
          new Blob([F], {
            type: L,
          }),
        );
      }
    }
    parseTextures(y) {
      const b = new Map();
      if ("Texture" in Gt.Objects) {
        const E = Gt.Objects.Texture;
        for (const T in E) {
          const L = this.parseTexture(E[T], y);
          b.set(parseInt(T), L);
        }
      }
      return b;
    }
    parseTexture(y, b) {
      const E = this.loadTexture(y, b);
      ((E.ID = y.id), (E.name = y.attrName));
      const T = y.WrapModeU,
        L = y.WrapModeV,
        F = T !== void 0 ? T.value : 0,
        j = L !== void 0 ? L.value : 0;
      if (
        ((E.wrapS = F === 0 ? m.rpg : m.uWy), (E.wrapT = j === 0 ? m.rpg : m.uWy), "Scaling" in y)
      ) {
        const W = y.Scaling.value;
        ((E.repeat.x = W[0]), (E.repeat.y = W[1]));
      }
      if ("Translation" in y) {
        const W = y.Translation.value;
        ((E.offset.x = W[0]), (E.offset.y = W[1]));
      }
      return E;
    }
    loadTexture(y, b) {
      let E;
      const T = this.textureLoader.path,
        L = On.get(y.id).children;
      L !== void 0 &&
        L.length > 0 &&
        b[L[0].ID] !== void 0 &&
        ((E = b[L[0].ID]),
        (E.indexOf("blob:") === 0 || E.indexOf("data:") === 0) &&
          this.textureLoader.setPath(void 0));
      let F;
      const j = y.FileName.slice(-3).toLowerCase();
      if (j === "tga") {
        const W = this.manager.getHandler(".tga");
        W === null
          ? (console.warn(
              "FBXLoader: TGA loader not found, creating placeholder texture for",
              y.RelativeFilename,
            ),
            (F = new m.xEZ()))
          : (W.setPath(this.textureLoader.path), (F = W.load(E)));
      } else
        j === "psd"
          ? (console.warn(
              "FBXLoader: PSD textures are not supported, creating placeholder texture for",
              y.RelativeFilename,
            ),
            (F = new m.xEZ()))
          : (F = this.textureLoader.load(E));
      return (this.textureLoader.setPath(T), F);
    }
    parseMaterials(y) {
      const b = new Map();
      if ("Material" in Gt.Objects) {
        const E = Gt.Objects.Material;
        for (const T in E) {
          const L = this.parseMaterial(E[T], y);
          L !== null && b.set(parseInt(T), L);
        }
      }
      return b;
    }
    parseMaterial(y, b) {
      const E = y.id,
        T = y.attrName;
      let L = y.ShadingModel;
      if ((typeof L == "object" && (L = L.value), !On.has(E))) return null;
      const F = this.parseParameters(y, b, E);
      let j;
      switch (L.toLowerCase()) {
        case "phong":
          j = new m.xoR();
          break;
        case "lambert":
          j = new m.YBo();
          break;
        default:
          (console.warn(
            'THREE.FBXLoader: unknown material type "%s". Defaulting to MeshPhongMaterial.',
            L,
          ),
            (j = new m.xoR()));
          break;
      }
      return (j.setValues(F), (j.name = T), j);
    }
    parseParameters(y, b, E) {
      const T = {};
      (y.BumpFactor && (T.bumpScale = y.BumpFactor.value),
        y.Diffuse
          ? (T.color = new m.Ilk().fromArray(y.Diffuse.value))
          : y.DiffuseColor &&
            (y.DiffuseColor.type === "Color" || y.DiffuseColor.type === "ColorRGB") &&
            (T.color = new m.Ilk().fromArray(y.DiffuseColor.value)),
        y.DisplacementFactor && (T.displacementScale = y.DisplacementFactor.value),
        y.Emissive
          ? (T.emissive = new m.Ilk().fromArray(y.Emissive.value))
          : y.EmissiveColor &&
            (y.EmissiveColor.type === "Color" || y.EmissiveColor.type === "ColorRGB") &&
            (T.emissive = new m.Ilk().fromArray(y.EmissiveColor.value)),
        y.EmissiveFactor && (T.emissiveIntensity = parseFloat(y.EmissiveFactor.value)),
        y.Opacity && (T.opacity = parseFloat(y.Opacity.value)),
        T.opacity < 1 && (T.transparent = !0),
        y.ReflectionFactor && (T.reflectivity = y.ReflectionFactor.value),
        y.Shininess && (T.shininess = y.Shininess.value),
        y.Specular
          ? (T.specular = new m.Ilk().fromArray(y.Specular.value))
          : y.SpecularColor &&
            y.SpecularColor.type === "Color" &&
            (T.specular = new m.Ilk().fromArray(y.SpecularColor.value)));
      const L = this;
      return (
        On.get(E).children.forEach(function (F) {
          const j = F.relationship;
          switch (j) {
            case "Bump":
              T.bumpMap = L.getTexture(b, F.ID);
              break;
            case "Maya|TEX_ao_map":
              T.aoMap = L.getTexture(b, F.ID);
              break;
            case "DiffuseColor":
            case "Maya|TEX_color_map":
              ((T.map = L.getTexture(b, F.ID)), T.map !== void 0 && (T.map.encoding = m.knz));
              break;
            case "DisplacementColor":
              T.displacementMap = L.getTexture(b, F.ID);
              break;
            case "EmissiveColor":
              ((T.emissiveMap = L.getTexture(b, F.ID)),
                T.emissiveMap !== void 0 && (T.emissiveMap.encoding = m.knz));
              break;
            case "NormalMap":
            case "Maya|TEX_normal_map":
              T.normalMap = L.getTexture(b, F.ID);
              break;
            case "ReflectionColor":
              ((T.envMap = L.getTexture(b, F.ID)),
                T.envMap !== void 0 && ((T.envMap.mapping = m.dSO), (T.envMap.encoding = m.knz)));
              break;
            case "SpecularColor":
              ((T.specularMap = L.getTexture(b, F.ID)),
                T.specularMap !== void 0 && (T.specularMap.encoding = m.knz));
              break;
            case "TransparentColor":
            case "TransparencyFactor":
              ((T.alphaMap = L.getTexture(b, F.ID)), (T.transparent = !0));
              break;
            case "AmbientColor":
            case "ShininessExponent":
            case "SpecularFactor":
            case "VectorDisplacementColor":
            default:
              console.warn(
                "THREE.FBXLoader: %s map is not supported in three.js, skipping texture.",
                j,
              );
              break;
          }
        }),
        T
      );
    }
    getTexture(y, b) {
      return (
        "LayeredTexture" in Gt.Objects &&
          b in Gt.Objects.LayeredTexture &&
          (console.warn(
            "THREE.FBXLoader: layered textures are not supported in three.js. Discarding all but first layer.",
          ),
          (b = On.get(b).children[0].ID)),
        y.get(b)
      );
    }
    parseDeformers() {
      const y = {},
        b = {};
      if ("Deformer" in Gt.Objects) {
        const E = Gt.Objects.Deformer;
        for (const T in E) {
          const L = E[T],
            F = On.get(parseInt(T));
          if (L.attrType === "Skin") {
            const j = this.parseSkeleton(F, E);
            ((j.ID = T),
              F.parents.length > 1 &&
                console.warn(
                  "THREE.FBXLoader: skeleton attached to more than one geometry is not supported.",
                ),
              (j.geometryID = F.parents[0].ID),
              (y[T] = j));
          } else if (L.attrType === "BlendShape") {
            const j = {
              id: T,
            };
            ((j.rawTargets = this.parseMorphTargets(F, E)),
              (j.id = T),
              F.parents.length > 1 &&
                console.warn(
                  "THREE.FBXLoader: morph target attached to more than one geometry is not supported.",
                ),
              (b[T] = j));
          }
        }
      }
      return {
        skeletons: y,
        morphTargets: b,
      };
    }
    parseSkeleton(y, b) {
      const E = [];
      return (
        y.children.forEach(function (T) {
          const L = b[T.ID];
          if (L.attrType !== "Cluster") return;
          const F = {
            ID: T.ID,
            indices: [],
            weights: [],
            transformLink: new m.yGw().fromArray(L.TransformLink.a),
          };
          ("Indexes" in L && ((F.indices = L.Indexes.a), (F.weights = L.Weights.a)), E.push(F));
        }),
        {
          rawBones: E,
          bones: [],
        }
      );
    }
    parseMorphTargets(y, b) {
      const E = [];
      for (let T = 0; T < y.children.length; T++) {
        const L = y.children[T],
          F = b[L.ID],
          j = {
            name: F.attrName,
            initialWeight: F.DeformPercent,
            id: F.id,
            fullWeights: F.FullWeights.a,
          };
        if (F.attrType !== "BlendShapeChannel") return;
        ((j.geoID = On.get(parseInt(L.ID)).children.filter(function (W) {
          return W.relationship === void 0;
        })[0].ID),
          E.push(j));
      }
      return E;
    }
    parseScene(y, b, E) {
      kn = new m.ZAu();
      const T = this.parseModels(y.skeletons, b, E),
        L = Gt.Objects.Model,
        F = this;
      (T.forEach(function (W) {
        const re = L[W.ID];
        (F.setLookAtProperties(W, re),
          On.get(W.ID).parents.forEach(function (te) {
            const Te = T.get(te.ID);
            Te !== void 0 && Te.add(W);
          }),
          W.parent === null && kn.add(W));
      }),
        this.bindSkeleton(y.skeletons, b, T),
        this.createAmbientLight(),
        kn.traverse(function (W) {
          if (W.userData.transformData) {
            W.parent &&
              ((W.userData.transformData.parentMatrix = W.parent.matrix),
              (W.userData.transformData.parentMatrixWorld = W.parent.matrixWorld));
            const re = Ao(W.userData.transformData);
            (W.applyMatrix4(re), W.updateWorldMatrix());
          }
        }));
      const j = new Fi().parse();
      (kn.children.length === 1 &&
        kn.children[0].isGroup &&
        ((kn.children[0].animations = j), (kn = kn.children[0])),
        (kn.animations = j));
    }
    parseModels(y, b, E) {
      const T = new Map(),
        L = Gt.Objects.Model;
      for (const F in L) {
        const j = parseInt(F),
          W = L[F],
          re = On.get(j);
        let fe = this.buildSkeleton(re, y, j, W.attrName);
        if (!fe) {
          switch (W.attrType) {
            case "Camera":
              fe = this.createCamera(re);
              break;
            case "Light":
              fe = this.createLight(re);
              break;
            case "Mesh":
              fe = this.createMesh(re, b, E);
              break;
            case "NurbsCurve":
              fe = this.createCurve(re, b);
              break;
            case "LimbNode":
            case "Root":
              fe = new m.N$j();
              break;
            case "Null":
            default:
              fe = new m.ZAu();
              break;
          }
          ((fe.name = W.attrName ? m.iUV.sanitizeNodeName(W.attrName) : ""), (fe.ID = j));
        }
        (this.getTransformData(fe, W), T.set(j, fe));
      }
      return T;
    }
    buildSkeleton(y, b, E, T) {
      let L = null;
      return (
        y.parents.forEach(function (F) {
          for (const j in b) {
            const W = b[j];
            W.rawBones.forEach(function (re, fe) {
              if (re.ID === F.ID) {
                const te = L;
                ((L = new m.N$j()),
                  L.matrixWorld.copy(re.transformLink),
                  (L.name = T ? m.iUV.sanitizeNodeName(T) : ""),
                  (L.ID = E),
                  (W.bones[fe] = L),
                  te !== null && L.add(te));
              }
            });
          }
        }),
        L
      );
    }
    createCamera(y) {
      let b, E;
      if (
        (y.children.forEach(function (T) {
          const L = Gt.Objects.NodeAttribute[T.ID];
          L !== void 0 && (E = L);
        }),
        E === void 0)
      )
        b = new m.Tme();
      else {
        let T = 0;
        E.CameraProjectionType !== void 0 && E.CameraProjectionType.value === 1 && (T = 1);
        let L = 1;
        E.NearPlane !== void 0 && (L = E.NearPlane.value / 1e3);
        let F = 1e3;
        E.FarPlane !== void 0 && (F = E.FarPlane.value / 1e3);
        let j = window.innerWidth,
          W = window.innerHeight;
        E.AspectWidth !== void 0 &&
          E.AspectHeight !== void 0 &&
          ((j = E.AspectWidth.value), (W = E.AspectHeight.value));
        const re = j / W;
        let fe = 45;
        E.FieldOfView !== void 0 && (fe = E.FieldOfView.value);
        const te = E.FocalLength ? E.FocalLength.value : null;
        switch (T) {
          case 0:
            ((b = new m.cPb(fe, re, L, F)), te !== null && b.setFocalLength(te));
            break;
          case 1:
            b = new m.iKG(-j / 2, j / 2, W / 2, -W / 2, L, F);
            break;
          default:
            (console.warn("THREE.FBXLoader: Unknown camera type " + T + "."), (b = new m.Tme()));
            break;
        }
      }
      return b;
    }
    createLight(y) {
      let b, E;
      if (
        (y.children.forEach(function (T) {
          const L = Gt.Objects.NodeAttribute[T.ID];
          L !== void 0 && (E = L);
        }),
        E === void 0)
      )
        b = new m.Tme();
      else {
        let T;
        E.LightType === void 0 ? (T = 0) : (T = E.LightType.value);
        let L = 16777215;
        E.Color !== void 0 && (L = new m.Ilk().fromArray(E.Color.value));
        let F = E.Intensity === void 0 ? 1 : E.Intensity.value / 100;
        E.CastLightOnObject !== void 0 && E.CastLightOnObject.value === 0 && (F = 0);
        let j = 0;
        E.FarAttenuationEnd !== void 0 &&
          (E.EnableFarAttenuation !== void 0 && E.EnableFarAttenuation.value === 0
            ? (j = 0)
            : (j = E.FarAttenuationEnd.value));
        const W = 1;
        switch (T) {
          case 0:
            b = new m.cek(L, F, j, W);
            break;
          case 1:
            b = new m.Ox3(L, F);
            break;
          case 2:
            let re = Math.PI / 3;
            E.InnerAngle !== void 0 && (re = m.M8C.degToRad(E.InnerAngle.value));
            let fe = 0;
            (E.OuterAngle !== void 0 &&
              ((fe = m.M8C.degToRad(E.OuterAngle.value)), (fe = Math.max(fe, 1))),
              (b = new m.PMe(L, F, j, re, fe, W)));
            break;
          default:
            (console.warn(
              "THREE.FBXLoader: Unknown light type " +
                E.LightType.value +
                ", defaulting to a PointLight.",
            ),
              (b = new m.cek(L, F)));
            break;
        }
        E.CastShadows !== void 0 && E.CastShadows.value === 1 && (b.castShadow = !0);
      }
      return b;
    }
    createMesh(y, b, E) {
      let T,
        L = null,
        F = null;
      const j = [];
      return (
        y.children.forEach(function (W) {
          (b.has(W.ID) && (L = b.get(W.ID)), E.has(W.ID) && j.push(E.get(W.ID)));
        }),
        j.length > 1
          ? (F = j)
          : j.length > 0
            ? (F = j[0])
            : ((F = new m.xoR({
                color: 13421772,
              })),
              j.push(F)),
        "color" in L.attributes &&
          j.forEach(function (W) {
            W.vertexColors = !0;
          }),
        L.FBX_Deformer ? ((T = new m.TUv(L, F)), T.normalizeSkinWeights()) : (T = new m.Kj0(L, F)),
        T
      );
    }
    createCurve(y, b) {
      const E = y.children.reduce(function (L, F) {
          return (b.has(F.ID) && (L = b.get(F.ID)), L);
        }, null),
        T = new m.nls({
          color: 3342591,
          linewidth: 1,
        });
      return new m.x12(E, T);
    }
    getTransformData(y, b) {
      const E = {};
      ("InheritType" in b && (E.inheritType = parseInt(b.InheritType.value)),
        "RotationOrder" in b ? (E.eulerOrder = Hi(b.RotationOrder.value)) : (E.eulerOrder = "ZYX"),
        "Lcl_Translation" in b && (E.translation = b.Lcl_Translation.value),
        "PreRotation" in b && (E.preRotation = b.PreRotation.value),
        "Lcl_Rotation" in b && (E.rotation = b.Lcl_Rotation.value),
        "PostRotation" in b && (E.postRotation = b.PostRotation.value),
        "Lcl_Scaling" in b && (E.scale = b.Lcl_Scaling.value),
        "ScalingOffset" in b && (E.scalingOffset = b.ScalingOffset.value),
        "ScalingPivot" in b && (E.scalingPivot = b.ScalingPivot.value),
        "RotationOffset" in b && (E.rotationOffset = b.RotationOffset.value),
        "RotationPivot" in b && (E.rotationPivot = b.RotationPivot.value),
        (y.userData.transformData = E));
    }
    setLookAtProperties(y, b) {
      "LookAtProperty" in b &&
        On.get(y.ID).children.forEach(function (T) {
          if (T.relationship === "LookAtProperty") {
            const L = Gt.Objects.Model[T.ID];
            if ("Lcl_Translation" in L) {
              const F = L.Lcl_Translation.value;
              y.target !== void 0
                ? (y.target.position.fromArray(F), kn.add(y.target))
                : y.lookAt(new m.Pa4().fromArray(F));
            }
          }
        });
    }
    bindSkeleton(y, b, E) {
      const T = this.parsePoseNodes();
      for (const L in y) {
        const F = y[L];
        On.get(parseInt(F.ID)).parents.forEach(function (W) {
          if (b.has(W.ID)) {
            const re = W.ID;
            On.get(re).parents.forEach(function (te) {
              E.has(te.ID) && E.get(te.ID).bind(new m.OdW(F.bones), T[te.ID]);
            });
          }
        });
      }
    }
    parsePoseNodes() {
      const y = {};
      if ("Pose" in Gt.Objects) {
        const b = Gt.Objects.Pose;
        for (const E in b)
          if (b[E].attrType === "BindPose" && b[E].NbPoseNodes > 0) {
            const T = b[E].PoseNode;
            Array.isArray(T)
              ? T.forEach(function (L) {
                  y[L.Node] = new m.yGw().fromArray(L.Matrix.a);
                })
              : (y[T.Node] = new m.yGw().fromArray(T.Matrix.a));
          }
      }
      return y;
    }
    createAmbientLight() {
      if ("GlobalSettings" in Gt && "AmbientColor" in Gt.GlobalSettings) {
        const y = Gt.GlobalSettings.AmbientColor.value,
          b = y[0],
          E = y[1],
          T = y[2];
        if (b !== 0 || E !== 0 || T !== 0) {
          const L = new m.Ilk(b, E, T);
          kn.add(new m.Mig(L, 1));
        }
      }
    }
  }
  class zr {
    constructor() {
      this.negativeMaterialIndices = !1;
    }
    parse(y) {
      const b = new Map();
      if ("Geometry" in Gt.Objects) {
        const E = Gt.Objects.Geometry;
        for (const T in E) {
          const L = On.get(parseInt(T)),
            F = this.parseGeometry(L, E[T], y);
          b.set(parseInt(T), F);
        }
      }
      return (
        this.negativeMaterialIndices === !0 &&
          console.warn(
            "THREE.FBXLoader: The FBX file contains invalid (negative) material indices. The asset might not render as expected.",
          ),
        b
      );
    }
    parseGeometry(y, b, E) {
      switch (b.attrType) {
        case "Mesh":
          return this.parseMeshGeometry(y, b, E);
        case "NurbsCurve":
          return this.parseNurbsGeometry(b);
      }
    }
    parseMeshGeometry(y, b, E) {
      const T = E.skeletons,
        L = [],
        F = y.parents.map(function (te) {
          return Gt.Objects.Model[te.ID];
        });
      if (F.length === 0) return;
      const j = y.children.reduce(function (te, Te) {
        return (T[Te.ID] !== void 0 && (te = T[Te.ID]), te);
      }, null);
      y.children.forEach(function (te) {
        E.morphTargets[te.ID] !== void 0 && L.push(E.morphTargets[te.ID]);
      });
      const W = F[0],
        re = {};
      ("RotationOrder" in W && (re.eulerOrder = Hi(W.RotationOrder.value)),
        "InheritType" in W && (re.inheritType = parseInt(W.InheritType.value)),
        "GeometricTranslation" in W && (re.translation = W.GeometricTranslation.value),
        "GeometricRotation" in W && (re.rotation = W.GeometricRotation.value),
        "GeometricScaling" in W && (re.scale = W.GeometricScaling.value));
      const fe = Ao(re);
      return this.genGeometry(b, j, L, fe);
    }
    genGeometry(y, b, E, T) {
      const L = new m.u9r();
      y.attrName && (L.name = y.attrName);
      const F = this.parseGeoNode(y, b),
        j = this.genBuffers(F),
        W = new m.a$l(j.vertex, 3);
      if (
        (W.applyMatrix4(T),
        L.setAttribute("position", W),
        j.colors.length > 0 && L.setAttribute("color", new m.a$l(j.colors, 3)),
        b &&
          (L.setAttribute("skinIndex", new m.qlB(j.weightsIndices, 4)),
          L.setAttribute("skinWeight", new m.a$l(j.vertexWeights, 4)),
          (L.FBX_Deformer = b)),
        j.normal.length > 0)
      ) {
        const re = new m.Vkp().getNormalMatrix(T),
          fe = new m.a$l(j.normal, 3);
        (fe.applyNormalMatrix(re), L.setAttribute("normal", fe));
      }
      if (
        (j.uvs.forEach(function (re, fe) {
          let te = "uv" + (fe + 1).toString();
          (fe === 0 && (te = "uv"), L.setAttribute(te, new m.a$l(j.uvs[fe], 2)));
        }),
        F.material && F.material.mappingType !== "AllSame")
      ) {
        let re = j.materialIndex[0],
          fe = 0;
        if (
          (j.materialIndex.forEach(function (te, Te) {
            te !== re && (L.addGroup(fe, Te - fe, re), (re = te), (fe = Te));
          }),
          L.groups.length > 0)
        ) {
          const te = L.groups[L.groups.length - 1],
            Te = te.start + te.count;
          Te !== j.materialIndex.length && L.addGroup(Te, j.materialIndex.length - Te, re);
        }
        L.groups.length === 0 && L.addGroup(0, j.materialIndex.length, j.materialIndex[0]);
      }
      return (this.addMorphTargets(L, y, E, T), L);
    }
    parseGeoNode(y, b) {
      const E = {};
      if (
        ((E.vertexPositions = y.Vertices !== void 0 ? y.Vertices.a : []),
        (E.vertexIndices = y.PolygonVertexIndex !== void 0 ? y.PolygonVertexIndex.a : []),
        y.LayerElementColor && (E.color = this.parseVertexColors(y.LayerElementColor[0])),
        y.LayerElementMaterial &&
          (E.material = this.parseMaterialIndices(y.LayerElementMaterial[0])),
        y.LayerElementNormal && (E.normal = this.parseNormals(y.LayerElementNormal[0])),
        y.LayerElementUV)
      ) {
        E.uv = [];
        let T = 0;
        for (; y.LayerElementUV[T];)
          (y.LayerElementUV[T].UV && E.uv.push(this.parseUVs(y.LayerElementUV[T])), T++);
      }
      return (
        (E.weightTable = {}),
        b !== null &&
          ((E.skeleton = b),
          b.rawBones.forEach(function (T, L) {
            T.indices.forEach(function (F, j) {
              (E.weightTable[F] === void 0 && (E.weightTable[F] = []),
                E.weightTable[F].push({
                  id: L,
                  weight: T.weights[j],
                }));
            });
          })),
        E
      );
    }
    genBuffers(y) {
      const b = {
        vertex: [],
        normal: [],
        colors: [],
        uvs: [],
        materialIndex: [],
        vertexWeights: [],
        weightsIndices: [],
      };
      let E = 0,
        T = 0,
        L = !1,
        F = [],
        j = [],
        W = [],
        re = [],
        fe = [],
        te = [];
      const Te = this;
      return (
        y.vertexIndices.forEach(function (Ge, St) {
          let kt,
            Vt = !1;
          Ge < 0 && ((Ge = Ge ^ -1), (Vt = !0));
          let gt = [],
            xt = [];
          if ((F.push(Ge * 3, Ge * 3 + 1, Ge * 3 + 2), y.color)) {
            const Xe = qi(St, E, Ge, y.color);
            W.push(Xe[0], Xe[1], Xe[2]);
          }
          if (y.skeleton) {
            if (
              (y.weightTable[Ge] !== void 0 &&
                y.weightTable[Ge].forEach(function (Xe) {
                  (xt.push(Xe.weight), gt.push(Xe.id));
                }),
              xt.length > 4)
            ) {
              L ||
                (console.warn(
                  "THREE.FBXLoader: Vertex has more than 4 skinning weights assigned to vertex. Deleting additional weights.",
                ),
                (L = !0));
              const Xe = [0, 0, 0, 0],
                ut = [0, 0, 0, 0];
              (xt.forEach(function (dn, qt) {
                let ln = dn,
                  Tn = gt[qt];
                ut.forEach(function (fn, Hn, En) {
                  if (ln > fn) {
                    ((En[Hn] = ln), (ln = fn));
                    const Ei = Xe[Hn];
                    ((Xe[Hn] = Tn), (Tn = Ei));
                  }
                });
              }),
                (gt = Xe),
                (xt = ut));
            }
            for (; xt.length < 4;) (xt.push(0), gt.push(0));
            for (let Xe = 0; Xe < 4; ++Xe) (fe.push(xt[Xe]), te.push(gt[Xe]));
          }
          if (y.normal) {
            const Xe = qi(St, E, Ge, y.normal);
            j.push(Xe[0], Xe[1], Xe[2]);
          }
          (y.material &&
            y.material.mappingType !== "AllSame" &&
            ((kt = qi(St, E, Ge, y.material)[0]),
            kt < 0 && ((Te.negativeMaterialIndices = !0), (kt = 0))),
            y.uv &&
              y.uv.forEach(function (Xe, ut) {
                const dn = qi(St, E, Ge, Xe);
                (re[ut] === void 0 && (re[ut] = []), re[ut].push(dn[0]), re[ut].push(dn[1]));
              }),
            T++,
            Vt &&
              (T > 4 &&
                console.warn(
                  "THREE.FBXLoader: Polygons with more than four sides are not supported. Make sure to triangulate the geometry during export.",
                ),
              Te.genFace(b, y, F, kt, j, W, re, fe, te, T),
              E++,
              (T = 0),
              (F = []),
              (j = []),
              (W = []),
              (re = []),
              (fe = []),
              (te = [])));
        }),
        b
      );
    }
    genFace(y, b, E, T, L, F, j, W, re, fe) {
      for (let te = 2; te < fe; te++)
        (y.vertex.push(b.vertexPositions[E[0]]),
          y.vertex.push(b.vertexPositions[E[1]]),
          y.vertex.push(b.vertexPositions[E[2]]),
          y.vertex.push(b.vertexPositions[E[(te - 1) * 3]]),
          y.vertex.push(b.vertexPositions[E[(te - 1) * 3 + 1]]),
          y.vertex.push(b.vertexPositions[E[(te - 1) * 3 + 2]]),
          y.vertex.push(b.vertexPositions[E[te * 3]]),
          y.vertex.push(b.vertexPositions[E[te * 3 + 1]]),
          y.vertex.push(b.vertexPositions[E[te * 3 + 2]]),
          b.skeleton &&
            (y.vertexWeights.push(W[0]),
            y.vertexWeights.push(W[1]),
            y.vertexWeights.push(W[2]),
            y.vertexWeights.push(W[3]),
            y.vertexWeights.push(W[(te - 1) * 4]),
            y.vertexWeights.push(W[(te - 1) * 4 + 1]),
            y.vertexWeights.push(W[(te - 1) * 4 + 2]),
            y.vertexWeights.push(W[(te - 1) * 4 + 3]),
            y.vertexWeights.push(W[te * 4]),
            y.vertexWeights.push(W[te * 4 + 1]),
            y.vertexWeights.push(W[te * 4 + 2]),
            y.vertexWeights.push(W[te * 4 + 3]),
            y.weightsIndices.push(re[0]),
            y.weightsIndices.push(re[1]),
            y.weightsIndices.push(re[2]),
            y.weightsIndices.push(re[3]),
            y.weightsIndices.push(re[(te - 1) * 4]),
            y.weightsIndices.push(re[(te - 1) * 4 + 1]),
            y.weightsIndices.push(re[(te - 1) * 4 + 2]),
            y.weightsIndices.push(re[(te - 1) * 4 + 3]),
            y.weightsIndices.push(re[te * 4]),
            y.weightsIndices.push(re[te * 4 + 1]),
            y.weightsIndices.push(re[te * 4 + 2]),
            y.weightsIndices.push(re[te * 4 + 3])),
          b.color &&
            (y.colors.push(F[0]),
            y.colors.push(F[1]),
            y.colors.push(F[2]),
            y.colors.push(F[(te - 1) * 3]),
            y.colors.push(F[(te - 1) * 3 + 1]),
            y.colors.push(F[(te - 1) * 3 + 2]),
            y.colors.push(F[te * 3]),
            y.colors.push(F[te * 3 + 1]),
            y.colors.push(F[te * 3 + 2])),
          b.material &&
            b.material.mappingType !== "AllSame" &&
            (y.materialIndex.push(T), y.materialIndex.push(T), y.materialIndex.push(T)),
          b.normal &&
            (y.normal.push(L[0]),
            y.normal.push(L[1]),
            y.normal.push(L[2]),
            y.normal.push(L[(te - 1) * 3]),
            y.normal.push(L[(te - 1) * 3 + 1]),
            y.normal.push(L[(te - 1) * 3 + 2]),
            y.normal.push(L[te * 3]),
            y.normal.push(L[te * 3 + 1]),
            y.normal.push(L[te * 3 + 2])),
          b.uv &&
            b.uv.forEach(function (Te, Ge) {
              (y.uvs[Ge] === void 0 && (y.uvs[Ge] = []),
                y.uvs[Ge].push(j[Ge][0]),
                y.uvs[Ge].push(j[Ge][1]),
                y.uvs[Ge].push(j[Ge][(te - 1) * 2]),
                y.uvs[Ge].push(j[Ge][(te - 1) * 2 + 1]),
                y.uvs[Ge].push(j[Ge][te * 2]),
                y.uvs[Ge].push(j[Ge][te * 2 + 1]));
            }));
    }
    addMorphTargets(y, b, E, T) {
      if (E.length === 0) return;
      ((y.morphTargetsRelative = !0), (y.morphAttributes.position = []));
      const L = this;
      E.forEach(function (F) {
        F.rawTargets.forEach(function (j) {
          const W = Gt.Objects.Geometry[j.geoID];
          W !== void 0 && L.genMorphGeometry(y, b, W, T, j.name);
        });
      });
    }
    genMorphGeometry(y, b, E, T, L) {
      const F = b.PolygonVertexIndex !== void 0 ? b.PolygonVertexIndex.a : [],
        j = E.Vertices !== void 0 ? E.Vertices.a : [],
        W = E.Indexes !== void 0 ? E.Indexes.a : [],
        re = y.attributes.position.count * 3,
        fe = new Float32Array(re);
      for (let St = 0; St < W.length; St++) {
        const kt = W[St] * 3;
        ((fe[kt] = j[St * 3]), (fe[kt + 1] = j[St * 3 + 1]), (fe[kt + 2] = j[St * 3 + 2]));
      }
      const te = {
          vertexIndices: F,
          vertexPositions: fe,
        },
        Te = this.genBuffers(te),
        Ge = new m.a$l(Te.vertex, 3);
      ((Ge.name = L || E.attrName), Ge.applyMatrix4(T), y.morphAttributes.position.push(Ge));
    }
    parseNormals(y) {
      const b = y.MappingInformationType,
        E = y.ReferenceInformationType,
        T = y.Normals.a;
      let L = [];
      return (
        E === "IndexToDirect" &&
          ("NormalIndex" in y
            ? (L = y.NormalIndex.a)
            : "NormalsIndex" in y && (L = y.NormalsIndex.a)),
        {
          dataSize: 3,
          buffer: T,
          indices: L,
          mappingType: b,
          referenceType: E,
        }
      );
    }
    parseUVs(y) {
      const b = y.MappingInformationType,
        E = y.ReferenceInformationType,
        T = y.UV.a;
      let L = [];
      return (
        E === "IndexToDirect" && (L = y.UVIndex.a),
        {
          dataSize: 2,
          buffer: T,
          indices: L,
          mappingType: b,
          referenceType: E,
        }
      );
    }
    parseVertexColors(y) {
      const b = y.MappingInformationType,
        E = y.ReferenceInformationType,
        T = y.Colors.a;
      let L = [];
      return (
        E === "IndexToDirect" && (L = y.ColorIndex.a),
        {
          dataSize: 4,
          buffer: T,
          indices: L,
          mappingType: b,
          referenceType: E,
        }
      );
    }
    parseMaterialIndices(y) {
      const b = y.MappingInformationType,
        E = y.ReferenceInformationType;
      if (b === "NoMappingInformation")
        return {
          dataSize: 1,
          buffer: [0],
          indices: [0],
          mappingType: "AllSame",
          referenceType: E,
        };
      const T = y.Materials.a,
        L = [];
      for (let F = 0; F < T.length; ++F) L.push(F);
      return {
        dataSize: 1,
        buffer: T,
        indices: L,
        mappingType: b,
        referenceType: E,
      };
    }
    parseNurbsGeometry(y) {
      const b = parseInt(y.Order);
      if (isNaN(b))
        return (
          console.error(
            "THREE.FBXLoader: Invalid Order %s given for geometry ID: %s",
            y.Order,
            y.id,
          ),
          new m.u9r()
        );
      const E = b - 1,
        T = y.KnotVector.a,
        L = [],
        F = y.Points.a;
      for (let te = 0, Te = F.length; te < Te; te += 4) L.push(new m.Ltg().fromArray(F, te));
      let j, W;
      if (y.Form === "Closed") L.push(L[0]);
      else if (y.Form === "Periodic") {
        ((j = E), (W = T.length - 1 - j));
        for (let te = 0; te < E; ++te) L.push(L[te]);
      }
      const fe = new Si(E, T, L, j, W).getPoints(L.length * 12);
      return new m.u9r().setFromPoints(fe);
    }
  }
  class Fi {
    parse() {
      const y = [],
        b = this.parseClips();
      if (b !== void 0)
        for (const E in b) {
          const T = b[E],
            L = this.addClip(T);
          y.push(L);
        }
      return y;
    }
    parseClips() {
      if (Gt.Objects.AnimationCurve === void 0) return;
      const y = this.parseAnimationCurveNodes();
      this.parseAnimationCurves(y);
      const b = this.parseAnimationLayers(y);
      return this.parseAnimStacks(b);
    }
    parseAnimationCurveNodes() {
      const y = Gt.Objects.AnimationCurveNode,
        b = new Map();
      for (const E in y) {
        const T = y[E];
        if (T.attrName.match(/S|R|T|DeformPercent/) !== null) {
          const L = {
            id: T.id,
            attr: T.attrName,
            curves: {},
          };
          b.set(L.id, L);
        }
      }
      return b;
    }
    parseAnimationCurves(y) {
      const b = Gt.Objects.AnimationCurve;
      for (const E in b) {
        const T = {
            id: b[E].id,
            times: b[E].KeyTime.a.map(Ti),
            values: b[E].KeyValueFloat.a,
          },
          L = On.get(T.id);
        if (L !== void 0) {
          const F = L.parents[0].ID,
            j = L.parents[0].relationship;
          j.match(/X/)
            ? (y.get(F).curves.x = T)
            : j.match(/Y/)
              ? (y.get(F).curves.y = T)
              : j.match(/Z/)
                ? (y.get(F).curves.z = T)
                : j.match(/d|DeformPercent/) && y.has(F) && (y.get(F).curves.morph = T);
        }
      }
    }
    parseAnimationLayers(y) {
      const b = Gt.Objects.AnimationLayer,
        E = new Map();
      for (const T in b) {
        const L = [],
          F = On.get(parseInt(T));
        F !== void 0 &&
          (F.children.forEach(function (W, re) {
            if (y.has(W.ID)) {
              const fe = y.get(W.ID);
              if (fe.curves.x !== void 0 || fe.curves.y !== void 0 || fe.curves.z !== void 0) {
                if (L[re] === void 0) {
                  const te = On.get(W.ID).parents.filter(function (Te) {
                    return Te.relationship !== void 0;
                  })[0].ID;
                  if (te !== void 0) {
                    const Te = Gt.Objects.Model[te.toString()];
                    if (Te === void 0) {
                      console.warn("THREE.FBXLoader: Encountered a unused curve.", W);
                      return;
                    }
                    const Ge = {
                      modelName: Te.attrName ? m.iUV.sanitizeNodeName(Te.attrName) : "",
                      ID: Te.id,
                      initialPosition: [0, 0, 0],
                      initialRotation: [0, 0, 0],
                      initialScale: [1, 1, 1],
                    };
                    (kn.traverse(function (St) {
                      St.ID === Te.id &&
                        ((Ge.transform = St.matrix),
                        St.userData.transformData &&
                          (Ge.eulerOrder = St.userData.transformData.eulerOrder));
                    }),
                      Ge.transform || (Ge.transform = new m.yGw()),
                      "PreRotation" in Te && (Ge.preRotation = Te.PreRotation.value),
                      "PostRotation" in Te && (Ge.postRotation = Te.PostRotation.value),
                      (L[re] = Ge));
                  }
                }
                L[re] && (L[re][fe.attr] = fe);
              } else if (fe.curves.morph !== void 0) {
                if (L[re] === void 0) {
                  const te = On.get(W.ID).parents.filter(function (gt) {
                      return gt.relationship !== void 0;
                    })[0].ID,
                    Te = On.get(te).parents[0].ID,
                    Ge = On.get(Te).parents[0].ID,
                    St = On.get(Ge).parents[0].ID,
                    kt = Gt.Objects.Model[St],
                    Vt = {
                      modelName: kt.attrName ? m.iUV.sanitizeNodeName(kt.attrName) : "",
                      morphName: Gt.Objects.Deformer[te].attrName,
                    };
                  L[re] = Vt;
                }
                L[re][fe.attr] = fe;
              }
            }
          }),
          E.set(parseInt(T), L));
      }
      return E;
    }
    parseAnimStacks(y) {
      const b = Gt.Objects.AnimationStack,
        E = {};
      for (const T in b) {
        const L = On.get(parseInt(T)).children;
        L.length > 1 &&
          console.warn(
            "THREE.FBXLoader: Encountered an animation stack with multiple layers, this is currently not supported. Ignoring subsequent layers.",
          );
        const F = y.get(L[0].ID);
        E[T] = {
          name: b[T].attrName,
          layer: F,
        };
      }
      return E;
    }
    addClip(y) {
      let b = [];
      const E = this;
      return (
        y.layer.forEach(function (T) {
          b = b.concat(E.generateTracks(T));
        }),
        new m.m7l(y.name, -1, b)
      );
    }
    generateTracks(y) {
      const b = [];
      let E = new m.Pa4(),
        T = new m._fP(),
        L = new m.Pa4();
      if (
        (y.transform && y.transform.decompose(E, T, L),
        (E = E.toArray()),
        (T = new m.USm().setFromQuaternion(T, y.eulerOrder).toArray()),
        (L = L.toArray()),
        y.T !== void 0 && Object.keys(y.T.curves).length > 0)
      ) {
        const F = this.generateVectorTrack(y.modelName, y.T.curves, E, "position");
        F !== void 0 && b.push(F);
      }
      if (y.R !== void 0 && Object.keys(y.R.curves).length > 0) {
        const F = this.generateRotationTrack(
          y.modelName,
          y.R.curves,
          T,
          y.preRotation,
          y.postRotation,
          y.eulerOrder,
        );
        F !== void 0 && b.push(F);
      }
      if (y.S !== void 0 && Object.keys(y.S.curves).length > 0) {
        const F = this.generateVectorTrack(y.modelName, y.S.curves, L, "scale");
        F !== void 0 && b.push(F);
      }
      if (y.DeformPercent !== void 0) {
        const F = this.generateMorphTrack(y);
        F !== void 0 && b.push(F);
      }
      return b;
    }
    generateVectorTrack(y, b, E, T) {
      const L = this.getTimesForAllAxes(b),
        F = this.getKeyframeTrackValues(L, b, E);
      return new m.yC1(y + "." + T, L, F);
    }
    generateRotationTrack(y, b, E, T, L, F) {
      (b.x !== void 0 &&
        (this.interpolateRotations(b.x), (b.x.values = b.x.values.map(m.M8C.degToRad))),
        b.y !== void 0 &&
          (this.interpolateRotations(b.y), (b.y.values = b.y.values.map(m.M8C.degToRad))),
        b.z !== void 0 &&
          (this.interpolateRotations(b.z), (b.z.values = b.z.values.map(m.M8C.degToRad))));
      const j = this.getTimesForAllAxes(b),
        W = this.getKeyframeTrackValues(j, b, E);
      (T !== void 0 &&
        ((T = T.map(m.M8C.degToRad)),
        T.push(F),
        (T = new m.USm().fromArray(T)),
        (T = new m._fP().setFromEuler(T))),
        L !== void 0 &&
          ((L = L.map(m.M8C.degToRad)),
          L.push(F),
          (L = new m.USm().fromArray(L)),
          (L = new m._fP().setFromEuler(L).invert())));
      const re = new m._fP(),
        fe = new m.USm(),
        te = [];
      for (let Te = 0; Te < W.length; Te += 3)
        (fe.set(W[Te], W[Te + 1], W[Te + 2], F),
          re.setFromEuler(fe),
          T !== void 0 && re.premultiply(T),
          L !== void 0 && re.multiply(L),
          re.toArray(te, (Te / 3) * 4));
      return new m.iLg(y + ".quaternion", j, te);
    }
    generateMorphTrack(y) {
      const b = y.DeformPercent.curves.morph,
        E = b.values.map(function (L) {
          return L / 100;
        }),
        T = kn.getObjectByName(y.modelName).morphTargetDictionary[y.morphName];
      return new m.dUE(y.modelName + ".morphTargetInfluences[" + T + "]", b.times, E);
    }
    getTimesForAllAxes(y) {
      let b = [];
      if (
        (y.x !== void 0 && (b = b.concat(y.x.times)),
        y.y !== void 0 && (b = b.concat(y.y.times)),
        y.z !== void 0 && (b = b.concat(y.z.times)),
        (b = b.sort(function (E, T) {
          return E - T;
        })),
        b.length > 1)
      ) {
        let E = 1,
          T = b[0];
        for (let L = 1; L < b.length; L++) {
          const F = b[L];
          F !== T && ((b[E] = F), (T = F), E++);
        }
        b = b.slice(0, E);
      }
      return b;
    }
    getKeyframeTrackValues(y, b, E) {
      const T = E,
        L = [];
      let F = -1,
        j = -1,
        W = -1;
      return (
        y.forEach(function (re) {
          if (
            (b.x && (F = b.x.times.indexOf(re)),
            b.y && (j = b.y.times.indexOf(re)),
            b.z && (W = b.z.times.indexOf(re)),
            F !== -1)
          ) {
            const fe = b.x.values[F];
            (L.push(fe), (T[0] = fe));
          } else L.push(T[0]);
          if (j !== -1) {
            const fe = b.y.values[j];
            (L.push(fe), (T[1] = fe));
          } else L.push(T[1]);
          if (W !== -1) {
            const fe = b.z.values[W];
            (L.push(fe), (T[2] = fe));
          } else L.push(T[2]);
        }),
        L
      );
    }
    interpolateRotations(y) {
      for (let b = 1; b < y.values.length; b++) {
        const E = y.values[b - 1],
          T = y.values[b] - E,
          L = Math.abs(T);
        if (L >= 180) {
          const F = L / 180,
            j = T / F;
          let W = E + j;
          const re = y.times[b - 1],
            te = (y.times[b] - re) / F;
          let Te = re + te;
          const Ge = [],
            St = [];
          for (; Te < y.times[b];) (Ge.push(Te), (Te += te), St.push(W), (W += j));
          ((y.times = bs(y.times, b, Ge)), (y.values = bs(y.values, b, St)));
        }
      }
    }
  }
  class vr {
    getPrevNode() {
      return this.nodeStack[this.currentIndent - 2];
    }
    getCurrentNode() {
      return this.nodeStack[this.currentIndent - 1];
    }
    getCurrentProp() {
      return this.currentProp;
    }
    pushStack(y) {
      (this.nodeStack.push(y), (this.currentIndent += 1));
    }
    popStack() {
      (this.nodeStack.pop(), (this.currentIndent -= 1));
    }
    setCurrentProp(y, b) {
      ((this.currentProp = y), (this.currentPropName = b));
    }
    parse(y) {
      ((this.currentIndent = 0),
        (this.allNodes = new Gr()),
        (this.nodeStack = []),
        (this.currentProp = []),
        (this.currentPropName = ""));
      const b = this,
        E = y.split(/[\r\n]+/);
      return (
        E.forEach(function (T, L) {
          const F = T.match(/^[\s\t]*;/),
            j = T.match(/^[\s\t]*$/);
          if (F || j) return;
          const W = T.match("^\\t{" + b.currentIndent + "}(\\w+):(.*){", ""),
            re = T.match("^\\t{" + b.currentIndent + "}(\\w+):[\\s\\t\\r\\n](.*)"),
            fe = T.match("^\\t{" + (b.currentIndent - 1) + "}}");
          W
            ? b.parseNodeBegin(T, W)
            : re
              ? b.parseNodeProperty(T, re, E[++L])
              : fe
                ? b.popStack()
                : T.match(/^[^\s\t}]/) && b.parseNodePropertyContinued(T);
        }),
        this.allNodes
      );
    }
    parseNodeBegin(y, b) {
      const E = b[1].trim().replace(/^"/, "").replace(/"$/, ""),
        T = b[2].split(",").map(function (W) {
          return W.trim().replace(/^"/, "").replace(/"$/, "");
        }),
        L = {
          name: E,
        },
        F = this.parseNodeAttr(T),
        j = this.getCurrentNode();
      (this.currentIndent === 0
        ? this.allNodes.add(E, L)
        : E in j
          ? (E === "PoseNode"
              ? j.PoseNode.push(L)
              : j[E].id !== void 0 && ((j[E] = {}), (j[E][j[E].id] = j[E])),
            F.id !== "" && (j[E][F.id] = L))
          : typeof F.id == "number"
            ? ((j[E] = {}), (j[E][F.id] = L))
            : E !== "Properties70" && (E === "PoseNode" ? (j[E] = [L]) : (j[E] = L)),
        typeof F.id == "number" && (L.id = F.id),
        F.name !== "" && (L.attrName = F.name),
        F.type !== "" && (L.attrType = F.type),
        this.pushStack(L));
    }
    parseNodeAttr(y) {
      let b = y[0];
      y[0] !== "" && ((b = parseInt(y[0])), isNaN(b) && (b = y[0]));
      let E = "",
        T = "";
      return (
        y.length > 1 && ((E = y[1].replace(/^(\w+)::/, "")), (T = y[2])),
        {
          id: b,
          name: E,
          type: T,
        }
      );
    }
    parseNodeProperty(y, b, E) {
      let T = b[1].replace(/^"/, "").replace(/"$/, "").trim(),
        L = b[2].replace(/^"/, "").replace(/"$/, "").trim();
      T === "Content" && L === "," && (L = E.replace(/"/g, "").replace(/,$/, "").trim());
      const F = this.getCurrentNode();
      if (F.name === "Properties70") {
        this.parseNodeSpecialProperty(y, T, L);
        return;
      }
      if (T === "C") {
        const W = L.split(",").slice(1),
          re = parseInt(W[0]),
          fe = parseInt(W[1]);
        let te = L.split(",").slice(3);
        ((te = te.map(function (Te) {
          return Te.trim().replace(/^"/, "");
        })),
          (T = "connections"),
          (L = [re, fe]),
          Fr(L, te),
          F[T] === void 0 && (F[T] = []));
      }
      (T === "Node" && (F.id = L),
        T in F && Array.isArray(F[T]) ? F[T].push(L) : T !== "a" ? (F[T] = L) : (F.a = L),
        this.setCurrentProp(F, T),
        T === "a" && L.slice(-1) !== "," && (F.a = Us(L)));
    }
    parseNodePropertyContinued(y) {
      const b = this.getCurrentNode();
      ((b.a += y), y.slice(-1) !== "," && (b.a = Us(b.a)));
    }
    parseNodeSpecialProperty(y, b, E) {
      const T = E.split('",').map(function (fe) {
          return fe.trim().replace(/^\"/, "").replace(/\s/, "_");
        }),
        L = T[0],
        F = T[1],
        j = T[2],
        W = T[3];
      let re = T[4];
      switch (F) {
        case "int":
        case "enum":
        case "bool":
        case "ULongLong":
        case "double":
        case "Number":
        case "FieldOfView":
          re = parseFloat(re);
          break;
        case "Color":
        case "ColorRGB":
        case "Vector3D":
        case "Lcl_Translation":
        case "Lcl_Rotation":
        case "Lcl_Scaling":
          re = Us(re);
          break;
      }
      ((this.getPrevNode()[L] = {
        type: F,
        type2: j,
        flag: W,
        value: re,
      }),
        this.setCurrentProp(this.getPrevNode(), L));
    }
  }
  class Oi {
    parse(y) {
      const b = new ts(y);
      b.skip(23);
      const E = b.getUint32();
      if (E < 6400)
        throw new Error("THREE.FBXLoader: FBX version not supported, FileVersion: " + E);
      const T = new Gr();
      for (; !this.endOfContent(b);) {
        const L = this.parseNode(b, E);
        L !== null && T.add(L.name, L);
      }
      return T;
    }
    endOfContent(y) {
      return y.size() % 16 === 0
        ? ((y.getOffset() + 160 + 16) & -16) >= y.size()
        : y.getOffset() + 160 + 16 >= y.size();
    }
    parseNode(y, b) {
      const E = {},
        T = b >= 7500 ? y.getUint64() : y.getUint32(),
        L = b >= 7500 ? y.getUint64() : y.getUint32();
      b >= 7500 ? y.getUint64() : y.getUint32();
      const F = y.getUint8(),
        j = y.getString(F);
      if (T === 0) return null;
      const W = [];
      for (let Te = 0; Te < L; Te++) W.push(this.parseProperty(y));
      const re = W.length > 0 ? W[0] : "",
        fe = W.length > 1 ? W[1] : "",
        te = W.length > 2 ? W[2] : "";
      for (E.singleProperty = L === 1 && y.getOffset() === T; T > y.getOffset();) {
        const Te = this.parseNode(y, b);
        Te !== null && this.parseSubNode(j, E, Te);
      }
      return (
        (E.propertyList = W),
        typeof re == "number" && (E.id = re),
        fe !== "" && (E.attrName = fe),
        te !== "" && (E.attrType = te),
        j !== "" && (E.name = j),
        E
      );
    }
    parseSubNode(y, b, E) {
      if (E.singleProperty === !0) {
        const T = E.propertyList[0];
        Array.isArray(T) ? ((b[E.name] = E), (E.a = T)) : (b[E.name] = T);
      } else if (y === "Connections" && E.name === "C") {
        const T = [];
        (E.propertyList.forEach(function (L, F) {
          F !== 0 && T.push(L);
        }),
          b.connections === void 0 && (b.connections = []),
          b.connections.push(T));
      } else if (E.name === "Properties70")
        Object.keys(E).forEach(function (L) {
          b[L] = E[L];
        });
      else if (y === "Properties70" && E.name === "P") {
        let T = E.propertyList[0],
          L = E.propertyList[1];
        const F = E.propertyList[2],
          j = E.propertyList[3];
        let W;
        (T.indexOf("Lcl ") === 0 && (T = T.replace("Lcl ", "Lcl_")),
          L.indexOf("Lcl ") === 0 && (L = L.replace("Lcl ", "Lcl_")),
          L === "Color" ||
          L === "ColorRGB" ||
          L === "Vector" ||
          L === "Vector3D" ||
          L.indexOf("Lcl_") === 0
            ? (W = [E.propertyList[4], E.propertyList[5], E.propertyList[6]])
            : (W = E.propertyList[4]),
          (b[T] = {
            type: L,
            type2: F,
            flag: j,
            value: W,
          }));
      } else
        b[E.name] === void 0
          ? typeof E.id == "number"
            ? ((b[E.name] = {}), (b[E.name][E.id] = E))
            : (b[E.name] = E)
          : E.name === "PoseNode"
            ? (Array.isArray(b[E.name]) || (b[E.name] = [b[E.name]]), b[E.name].push(E))
            : b[E.name][E.id] === void 0 && (b[E.name][E.id] = E);
    }
    parseProperty(y) {
      const b = y.getString(1);
      let E;
      switch (b) {
        case "C":
          return y.getBoolean();
        case "D":
          return y.getFloat64();
        case "F":
          return y.getFloat32();
        case "I":
          return y.getInt32();
        case "L":
          return y.getInt64();
        case "R":
          return ((E = y.getUint32()), y.getArrayBuffer(E));
        case "S":
          return ((E = y.getUint32()), y.getString(E));
        case "Y":
          return y.getInt16();
        case "b":
        case "c":
        case "d":
        case "f":
        case "i":
        case "l":
          const T = y.getUint32(),
            L = y.getUint32(),
            F = y.getUint32();
          if (L === 0)
            switch (b) {
              case "b":
              case "c":
                return y.getBooleanArray(T);
              case "d":
                return y.getFloat64Array(T);
              case "f":
                return y.getFloat32Array(T);
              case "i":
                return y.getInt32Array(T);
              case "l":
                return y.getInt64Array(T);
            }
          const j = Xt(new Uint8Array(y.getArrayBuffer(F))),
            W = new ts(j.buffer);
          switch (b) {
            case "b":
            case "c":
              return W.getBooleanArray(T);
            case "d":
              return W.getFloat64Array(T);
            case "f":
              return W.getFloat32Array(T);
            case "i":
              return W.getInt32Array(T);
            case "l":
              return W.getInt64Array(T);
          }
          break;
        default:
          throw new Error("THREE.FBXLoader: Unknown property type " + b);
      }
    }
  }
  class ts {
    constructor(y, b) {
      ((this.dv = new DataView(y)),
        (this.offset = 0),
        (this.littleEndian = b !== void 0 ? b : !0),
        (this._textDecoder = new TextDecoder()));
    }
    getOffset() {
      return this.offset;
    }
    size() {
      return this.dv.buffer.byteLength;
    }
    skip(y) {
      this.offset += y;
    }
    getBoolean() {
      return (this.getUint8() & 1) === 1;
    }
    getBooleanArray(y) {
      const b = [];
      for (let E = 0; E < y; E++) b.push(this.getBoolean());
      return b;
    }
    getUint8() {
      const y = this.dv.getUint8(this.offset);
      return ((this.offset += 1), y);
    }
    getInt16() {
      const y = this.dv.getInt16(this.offset, this.littleEndian);
      return ((this.offset += 2), y);
    }
    getInt32() {
      const y = this.dv.getInt32(this.offset, this.littleEndian);
      return ((this.offset += 4), y);
    }
    getInt32Array(y) {
      const b = [];
      for (let E = 0; E < y; E++) b.push(this.getInt32());
      return b;
    }
    getUint32() {
      const y = this.dv.getUint32(this.offset, this.littleEndian);
      return ((this.offset += 4), y);
    }
    getInt64() {
      let y, b;
      return (
        this.littleEndian
          ? ((y = this.getUint32()), (b = this.getUint32()))
          : ((b = this.getUint32()), (y = this.getUint32())),
        b & 2147483648
          ? ((b = ~b & 4294967295),
            (y = ~y & 4294967295),
            y === 4294967295 && (b = (b + 1) & 4294967295),
            (y = (y + 1) & 4294967295),
            -(b * 4294967296 + y))
          : b * 4294967296 + y
      );
    }
    getInt64Array(y) {
      const b = [];
      for (let E = 0; E < y; E++) b.push(this.getInt64());
      return b;
    }
    getUint64() {
      let y, b;
      return (
        this.littleEndian
          ? ((y = this.getUint32()), (b = this.getUint32()))
          : ((b = this.getUint32()), (y = this.getUint32())),
        b * 4294967296 + y
      );
    }
    getFloat32() {
      const y = this.dv.getFloat32(this.offset, this.littleEndian);
      return ((this.offset += 4), y);
    }
    getFloat32Array(y) {
      const b = [];
      for (let E = 0; E < y; E++) b.push(this.getFloat32());
      return b;
    }
    getFloat64() {
      const y = this.dv.getFloat64(this.offset, this.littleEndian);
      return ((this.offset += 8), y);
    }
    getFloat64Array(y) {
      const b = [];
      for (let E = 0; E < y; E++) b.push(this.getFloat64());
      return b;
    }
    getArrayBuffer(y) {
      const b = this.dv.buffer.slice(this.offset, this.offset + y);
      return ((this.offset += y), b);
    }
    getString(y) {
      const b = this.offset;
      let E = new Uint8Array(this.dv.buffer, b, y);
      this.skip(y);
      const T = E.indexOf(0);
      return (T >= 0 && (E = new Uint8Array(this.dv.buffer, b, T)), this._textDecoder.decode(E));
    }
  }
  class Gr {
    add(y, b) {
      this[y] = b;
    }
  }
  function ys(ae) {
    const y = "Kaydara FBX Binary  \0";
    return ae.byteLength >= y.length && y === Ba(ae, 0, y.length);
  }
  function xs(ae) {
    const y = [
      "K",
      "a",
      "y",
      "d",
      "a",
      "r",
      "a",
      "\\",
      "F",
      "B",
      "X",
      "\\",
      "B",
      "i",
      "n",
      "a",
      "r",
      "y",
      "\\",
      "\\",
    ];
    let b = 0;
    function E(T) {
      const L = ae[T - 1];
      return ((ae = ae.slice(b + T)), b++, L);
    }
    for (let T = 0; T < y.length; ++T) if (E(1) === y[T]) return !1;
    return !0;
  }
  function hi(ae) {
    const y = /FBXVersion: (\d+)/,
      b = ae.match(y);
    if (b) return parseInt(b[1]);
    throw new Error("THREE.FBXLoader: Cannot find the version number for the file given.");
  }
  function Ti(ae) {
    return ae / 46186158e3;
  }
  const gi = [];
  function qi(ae, y, b, E) {
    let T;
    switch (E.mappingType) {
      case "ByPolygonVertex":
        T = ae;
        break;
      case "ByPolygon":
        T = y;
        break;
      case "ByVertice":
        T = b;
        break;
      case "AllSame":
        T = E.indices[0];
        break;
      default:
        console.warn("THREE.FBXLoader: unknown attribute mapping type " + E.mappingType);
    }
    E.referenceType === "IndexToDirect" && (T = E.indices[T]);
    const L = T * E.dataSize,
      F = L + E.dataSize;
    return Ns(gi, E.buffer, L, F);
  }
  const ks = new m.USm(),
    Gi = new m.Pa4();
  function Ao(ae) {
    const y = new m.yGw(),
      b = new m.yGw(),
      E = new m.yGw(),
      T = new m.yGw(),
      L = new m.yGw(),
      F = new m.yGw(),
      j = new m.yGw(),
      W = new m.yGw(),
      re = new m.yGw(),
      fe = new m.yGw(),
      te = new m.yGw(),
      Te = new m.yGw(),
      Ge = ae.inheritType ? ae.inheritType : 0;
    if ((ae.translation && y.setPosition(Gi.fromArray(ae.translation)), ae.preRotation)) {
      const Hn = ae.preRotation.map(m.M8C.degToRad);
      (Hn.push(ae.eulerOrder || m.USm.DEFAULT_ORDER), b.makeRotationFromEuler(ks.fromArray(Hn)));
    }
    if (ae.rotation) {
      const Hn = ae.rotation.map(m.M8C.degToRad);
      (Hn.push(ae.eulerOrder || m.USm.DEFAULT_ORDER), E.makeRotationFromEuler(ks.fromArray(Hn)));
    }
    if (ae.postRotation) {
      const Hn = ae.postRotation.map(m.M8C.degToRad);
      (Hn.push(ae.eulerOrder || m.USm.DEFAULT_ORDER),
        T.makeRotationFromEuler(ks.fromArray(Hn)),
        T.invert());
    }
    (ae.scale && L.scale(Gi.fromArray(ae.scale)),
      ae.scalingOffset && j.setPosition(Gi.fromArray(ae.scalingOffset)),
      ae.scalingPivot && F.setPosition(Gi.fromArray(ae.scalingPivot)),
      ae.rotationOffset && W.setPosition(Gi.fromArray(ae.rotationOffset)),
      ae.rotationPivot && re.setPosition(Gi.fromArray(ae.rotationPivot)),
      ae.parentMatrixWorld && (te.copy(ae.parentMatrix), fe.copy(ae.parentMatrixWorld)));
    const St = b.clone().multiply(E).multiply(T),
      kt = new m.yGw();
    kt.extractRotation(fe);
    const Vt = new m.yGw();
    Vt.copyPosition(fe);
    const gt = Vt.clone().invert().multiply(fe),
      xt = kt.clone().invert().multiply(gt),
      Xe = L,
      ut = new m.yGw();
    if (Ge === 0) ut.copy(kt).multiply(St).multiply(xt).multiply(Xe);
    else if (Ge === 1) ut.copy(kt).multiply(xt).multiply(St).multiply(Xe);
    else {
      const En = new m.yGw().scale(new m.Pa4().setFromMatrixScale(te)).clone().invert(),
        Ei = xt.clone().multiply(En);
      ut.copy(kt).multiply(St).multiply(Ei).multiply(Xe);
    }
    const dn = re.clone().invert(),
      qt = F.clone().invert();
    let ln = y
      .clone()
      .multiply(W)
      .multiply(re)
      .multiply(b)
      .multiply(E)
      .multiply(T)
      .multiply(dn)
      .multiply(j)
      .multiply(F)
      .multiply(L)
      .multiply(qt);
    const Tn = new m.yGw().copyPosition(ln),
      fn = fe.clone().multiply(Tn);
    return (Te.copyPosition(fn), (ln = Te.clone().multiply(ut)), ln.premultiply(fe.invert()), ln);
  }
  function Hi(ae) {
    ae = ae || 0;
    const y = ["ZYX", "YZX", "XZY", "ZXY", "YXZ", "XYZ"];
    return ae === 6
      ? (console.warn(
          "THREE.FBXLoader: unsupported Euler Order: Spherical XYZ. Animations and rotations may be incorrect.",
        ),
        y[0])
      : y[ae];
  }
  function Us(ae) {
    return ae.split(",").map(function (b) {
      return parseFloat(b);
    });
  }
  function Ba(ae, y, b) {
    return (
      y === void 0 && (y = 0),
      b === void 0 && (b = ae.byteLength),
      new TextDecoder().decode(new Uint8Array(ae, y, b))
    );
  }
  function Fr(ae, y) {
    for (let b = 0, E = ae.length, T = y.length; b < T; b++, E++) ae[E] = y[b];
  }
  function Ns(ae, y, b, E) {
    for (let T = b, L = 0; T < E; T++, L++) ae[L] = y[T];
    return ae;
  }
  function bs(ae, y, b) {
    return ae.slice(0, y).concat(b).concat(ae.slice(y));
  }
  var jo = r(774);
  class us extends s.g {
    constructor() {
      super(...arguments);
      B(this, "extensions", ["fbx"]);
    }
    load({ url: b, file: E, onLoad: T, onProgress: L, onError: F }) {
      const j = (W) => {
        (Object.assign(W.meshData, (0, jo.tQ)(W)), T(W));
      };
      new bi(this.viewer.loadingManager).load(b, j, L, F, E);
    }
  }
  const ha = new WeakMap();
  class da extends m.aNw {
    constructor(y) {
      (super(y),
        (this.decoderPath = ""),
        (this.decoderConfig = {}),
        (this.decoderBinary = null),
        (this.decoderPending = null),
        (this.workerLimit = 4),
        (this.workerPool = []),
        (this.workerNextTaskID = 1),
        (this.workerSourceURL = ""),
        (this.defaultAttributeIDs = {
          position: "POSITION",
          normal: "NORMAL",
          color: "COLOR",
          uv: "TEX_COORD",
        }),
        (this.defaultAttributeTypes = {
          position: "Float32Array",
          normal: "Float32Array",
          color: "Float32Array",
          uv: "Float32Array",
        }));
    }
    setDecoderPath(y) {
      return ((this.decoderPath = y), this);
    }
    setDecoderConfig(y) {
      return ((this.decoderConfig = y), this);
    }
    setWorkerLimit(y) {
      return ((this.workerLimit = y), this);
    }
    load(y, b, E, T) {
      const L = new m.hH6(this.manager);
      (L.setPath(this.path),
        L.setResponseType("arraybuffer"),
        L.setRequestHeader(this.requestHeader),
        L.setWithCredentials(this.withCredentials),
        L.load(
          y,
          (F) => {
            this.parse(F, b, T);
          },
          E,
          T,
        ));
    }
    parse(y, b, E) {
      this.decodeDracoFile(y, b, null, null, m.KI_).catch(E);
    }
    decodeDracoFile(y, b, E, T, L = m.GUF) {
      const F = {
        attributeIDs: E || this.defaultAttributeIDs,
        attributeTypes: T || this.defaultAttributeTypes,
        useUniqueIDs: !!E,
        vertexColorSpace: L,
      };
      return this.decodeGeometry(y, F).then(b);
    }
    decodeGeometry(y, b) {
      const E = JSON.stringify(b);
      if (ha.has(y)) {
        const W = ha.get(y);
        if (W.key === E) return W.promise;
        if (y.byteLength === 0)
          throw new Error(
            "THREE.DRACOLoader: Unable to re-decode a buffer with different settings. Buffer has already been transferred.",
          );
      }
      let T;
      const L = this.workerNextTaskID++,
        F = y.byteLength,
        j = this._getWorker(L, F)
          .then(
            (W) => (
              (T = W),
              new Promise((re, fe) => {
                ((T._callbacks[L] = {
                  resolve: re,
                  reject: fe,
                }),
                  T.postMessage(
                    {
                      type: "decode",
                      id: L,
                      taskConfig: b,
                      buffer: y,
                    },
                    [y],
                  ));
              })
            ),
          )
          .then((W) => this._createGeometry(W.geometry));
      return (
        j
          .catch(() => !0)
          .then(() => {
            T && L && this._releaseTask(T, L);
          }),
        ha.set(y, {
          key: E,
          promise: j,
        }),
        j
      );
    }
    _createGeometry(y) {
      const b = new m.u9r();
      y.index && b.setIndex(new m.TlE(y.index.array, 1));
      for (let E = 0; E < y.attributes.length; E++) {
        const T = y.attributes[E],
          L = T.name,
          F = T.array,
          j = T.itemSize,
          W = new m.TlE(F, j);
        (L === "color" && this._assignVertexColorSpace(W, T.vertexColorSpace),
          b.setAttribute(L, W));
      }
      return b;
    }
    _assignVertexColorSpace(y, b) {
      if (b !== m.KI_) return;
      const E = new m.Ilk();
      for (let T = 0, L = y.count; T < L; T++)
        (E.fromBufferAttribute(y, T).convertSRGBToLinear(), y.setXYZ(T, E.r, E.g, E.b));
    }
    _loadLibrary(y, b) {
      const E = new m.hH6(this.manager);
      return (
        E.setPath(this.decoderPath),
        E.setResponseType(b),
        E.setWithCredentials(this.withCredentials),
        new Promise((T, L) => {
          E.load(y, T, void 0, L);
        })
      );
    }
    preload() {
      return (this._initDecoder(), this);
    }
    _initDecoder() {
      if (this.decoderPending) return this.decoderPending;
      const y = typeof WebAssembly != "object" || this.decoderConfig.type === "js",
        b = [];
      return (
        y
          ? b.push(this._loadLibrary("draco_decoder.js", "text"))
          : (b.push(this._loadLibrary("draco_wasm_wrapper.js", "text")),
            b.push(this._loadLibrary("draco_decoder.wasm", "arraybuffer"))),
        (this.decoderPending = Promise.all(b).then((E) => {
          const T = E[0];
          y || (this.decoderConfig.wasmBinary = E[1]);
          const L = uo.toString(),
            F = [
              "/* draco decoder */",
              T,
              "",
              "/* worker */",
              L.substring(L.indexOf("{") + 1, L.lastIndexOf("}")),
            ].join(`
`);
          this.workerSourceURL = URL.createObjectURL(new Blob([F]));
        })),
        this.decoderPending
      );
    }
    _getWorker(y, b) {
      return this._initDecoder().then(() => {
        if (this.workerPool.length < this.workerLimit) {
          const T = new Worker(this.workerSourceURL);
          ((T._callbacks = {}),
            (T._taskCosts = {}),
            (T._taskLoad = 0),
            T.postMessage({
              type: "init",
              decoderConfig: this.decoderConfig,
            }),
            (T.onmessage = function (L) {
              const F = L.data;
              switch (F.type) {
                case "decode":
                  T._callbacks[F.id].resolve(F);
                  break;
                case "error":
                  T._callbacks[F.id].reject(F);
                  break;
                default:
                  console.error('THREE.DRACOLoader: Unexpected message, "' + F.type + '"');
              }
            }),
            this.workerPool.push(T));
        } else
          this.workerPool.sort(function (T, L) {
            return T._taskLoad > L._taskLoad ? -1 : 1;
          });
        const E = this.workerPool[this.workerPool.length - 1];
        return ((E._taskCosts[y] = b), (E._taskLoad += b), E);
      });
    }
    _releaseTask(y, b) {
      ((y._taskLoad -= y._taskCosts[b]), delete y._callbacks[b], delete y._taskCosts[b]);
    }
    debug() {
      console.log(
        "Task load: ",
        this.workerPool.map((y) => y._taskLoad),
      );
    }
    dispose() {
      for (let y = 0; y < this.workerPool.length; ++y) this.workerPool[y].terminate();
      return (
        (this.workerPool.length = 0),
        this.workerSourceURL !== "" && URL.revokeObjectURL(this.workerSourceURL),
        this
      );
    }
  }
  function uo() {
    let ae, y;
    onmessage = function (F) {
      const j = F.data;
      switch (j.type) {
        case "init":
          ((ae = j.decoderConfig),
            (y = new Promise(function (fe) {
              ((ae.onModuleLoaded = function (te) {
                fe({
                  draco: te,
                });
              }),
                DracoDecoderModule(ae));
            })));
          break;
        case "decode":
          const W = j.buffer,
            re = j.taskConfig;
          y.then((fe) => {
            const te = fe.draco,
              Te = new te.Decoder();
            try {
              const Ge = b(te, Te, new Int8Array(W), re),
                St = Ge.attributes.map((kt) => kt.array.buffer);
              (Ge.index && St.push(Ge.index.array.buffer),
                self.postMessage(
                  {
                    type: "decode",
                    id: j.id,
                    geometry: Ge,
                  },
                  St,
                ));
            } catch (Ge) {
              (console.error(Ge),
                self.postMessage({
                  type: "error",
                  id: j.id,
                  error: Ge.message,
                }));
            } finally {
              te.destroy(Te);
            }
          });
          break;
      }
    };
    function b(F, j, W, re) {
      const fe = re.attributeIDs,
        te = re.attributeTypes;
      let Te, Ge;
      const St = j.GetEncodedGeometryType(W);
      if (St === F.TRIANGULAR_MESH)
        ((Te = new F.Mesh()), (Ge = j.DecodeArrayToMesh(W, W.byteLength, Te)));
      else if (St === F.POINT_CLOUD)
        ((Te = new F.PointCloud()), (Ge = j.DecodeArrayToPointCloud(W, W.byteLength, Te)));
      else throw new Error("THREE.DRACOLoader: Unexpected geometry type.");
      if (!Ge.ok() || Te.ptr === 0)
        throw new Error("THREE.DRACOLoader: Decoding failed: " + Ge.error_msg());
      const kt = {
        index: null,
        attributes: [],
      };
      for (const Vt in fe) {
        const gt = self[te[Vt]];
        let xt, Xe;
        if (re.useUniqueIDs) ((Xe = fe[Vt]), (xt = j.GetAttributeByUniqueId(Te, Xe)));
        else {
          if (((Xe = j.GetAttributeId(Te, F[fe[Vt]])), Xe === -1)) continue;
          xt = j.GetAttribute(Te, Xe);
        }
        const ut = T(F, j, Te, Vt, gt, xt);
        (Vt === "color" && (ut.vertexColorSpace = re.vertexColorSpace), kt.attributes.push(ut));
      }
      return (St === F.TRIANGULAR_MESH && (kt.index = E(F, j, Te)), F.destroy(Te), kt);
    }
    function E(F, j, W) {
      const fe = W.num_faces() * 3,
        te = fe * 4,
        Te = F._malloc(te);
      j.GetTrianglesUInt32Array(W, te, Te);
      const Ge = new Uint32Array(F.HEAPF32.buffer, Te, fe).slice();
      return (
        F._free(Te),
        {
          array: Ge,
          itemSize: 1,
        }
      );
    }
    function T(F, j, W, re, fe, te) {
      const Te = te.num_components(),
        St = W.num_points() * Te,
        kt = St * fe.BYTES_PER_ELEMENT,
        Vt = L(F, fe),
        gt = F._malloc(kt);
      j.GetAttributeDataArrayForAllPoints(W, te, Vt, kt, gt);
      const xt = new fe(F.HEAPF32.buffer, gt, St).slice();
      return (
        F._free(gt),
        {
          name: re,
          array: xt,
          itemSize: Te,
        }
      );
    }
    function L(F, j) {
      switch (j) {
        case Float32Array:
          return F.DT_FLOAT32;
        case Int8Array:
          return F.DT_INT8;
        case Int16Array:
          return F.DT_INT16;
        case Int32Array:
          return F.DT_INT32;
        case Uint8Array:
          return F.DT_UINT8;
        case Uint16Array:
          return F.DT_UINT16;
        case Uint32Array:
          return F.DT_UINT32;
      }
    }
  }
  var Js = r(980);
  function So(ae, y) {
    if (y === m.WwZ)
      return (
        console.warn(
          "THREE.BufferGeometryUtils.toTrianglesDrawMode(): Geometry already defined as triangles.",
        ),
        ae
      );
    if (y === m.z$h || y === m.UlW) {
      let b = ae.getIndex();
      if (b === null) {
        const F = [],
          j = ae.getAttribute("position");
        if (j !== void 0) {
          for (let W = 0; W < j.count; W++) F.push(W);
          (ae.setIndex(F), (b = ae.getIndex()));
        } else
          return (
            console.error(
              "THREE.BufferGeometryUtils.toTrianglesDrawMode(): Undefined position attribute. Processing not possible.",
            ),
            ae
          );
      }
      const E = b.count - 2,
        T = [];
      if (y === m.z$h)
        for (let F = 1; F <= E; F++) (T.push(b.getX(0)), T.push(b.getX(F)), T.push(b.getX(F + 1)));
      else
        for (let F = 0; F < E; F++)
          F % 2 === 0
            ? (T.push(b.getX(F)), T.push(b.getX(F + 1)), T.push(b.getX(F + 2)))
            : (T.push(b.getX(F + 2)), T.push(b.getX(F + 1)), T.push(b.getX(F)));
      T.length / 3 !== E &&
        console.error(
          "THREE.BufferGeometryUtils.toTrianglesDrawMode(): Unable to generate correct amount of triangles.",
        );
      const L = ae.clone();
      return (L.setIndex(T), L.clearGroups(), L);
    } else
      return (
        console.error("THREE.BufferGeometryUtils.toTrianglesDrawMode(): Unknown draw mode:", y),
        ae
      );
  }
  class Fa extends m.aNw {
    constructor(y) {
      (super(y),
        (this.dracoLoader = null),
        (this.ktx2Loader = null),
        (this.meshoptDecoder = null),
        (this.pluginCallbacks = []),
        this.register(function (b) {
          return new al(b);
        }),
        this.register(function (b) {
          return new ul(b);
        }),
        this.register(function (b) {
          return new ka(b);
        }),
        this.register(function (b) {
          return new Ua(b);
        }),
        this.register(function (b) {
          return new ho(b);
        }),
        this.register(function (b) {
          return new Xl(b);
        }),
        this.register(function (b) {
          return new ll(b);
        }),
        this.register(function (b) {
          return new cl(b);
        }),
        this.register(function (b) {
          return new ol(b);
        }),
        this.register(function (b) {
          return new fa(b);
        }),
        this.register(function (b) {
          return new $s(b);
        }),
        this.register(function (b) {
          return new jl(b);
        }),
        this.register(function (b) {
          return new Na(b);
        }),
        this.register(function (b) {
          return new pa(b);
        }));
    }
    load(y, b, E, T, L) {
      const F = this;
      let j;
      (this.resourcePath !== ""
        ? (j = this.resourcePath)
        : this.path !== ""
          ? (j = this.path)
          : (j = m.Zp0.extractUrlBase(y)),
        this.manager.itemStart(y));
      const W = function (fe) {
          (T ? T(fe) : console.error(fe), F.manager.itemError(y), F.manager.itemEnd(y));
        },
        re = new m.hH6(this.manager);
      (re.setPath(this.path),
        re.setResponseType("arraybuffer"),
        re.setRequestHeader(this.requestHeader),
        re.setWithCredentials(this.withCredentials),
        re.load(
          y,
          function (fe) {
            try {
              F.parse(
                fe,
                j,
                function (te) {
                  (b(te), F.manager.itemEnd(y));
                },
                W,
                L == null ? void 0 : L.additionalFiles,
              );
            } catch (te) {
              W(te);
            }
          },
          E,
          W,
          L == null ? void 0 : L.mainFile,
        ));
    }
    setDRACOLoader(y) {
      return ((this.dracoLoader = y), this);
    }
    setDDSLoader() {
      throw new Error(
        'THREE.GLTFLoader: "MSFT_texture_dds" no longer supported. Please update to "KHR_texture_basisu".',
      );
    }
    setKTX2Loader(y) {
      return ((this.ktx2Loader = y), this);
    }
    setMeshoptDecoder(y) {
      return ((this.meshoptDecoder = y), this);
    }
    register(y) {
      return (this.pluginCallbacks.indexOf(y) === -1 && this.pluginCallbacks.push(y), this);
    }
    unregister(y) {
      return (
        this.pluginCallbacks.indexOf(y) !== -1 &&
          this.pluginCallbacks.splice(this.pluginCallbacks.indexOf(y), 1),
        this
      );
    }
    parse(y, b, E, T, L) {
      let F;
      const j = {},
        W = {},
        re = new TextDecoder();
      if (typeof y == "string") F = JSON.parse(y);
      else if (y instanceof ArrayBuffer) {
        const te = new Uint8Array(y, 0, 4).join("");
        if (te === ma || te === nr) {
          try {
            j[ti.KHR_BINARY_GLTF] = new dl(y);
          } catch (Te) {
            T && T(Te);
            return;
          }
          F = JSON.parse(j[ti.KHR_BINARY_GLTF].content);
        } else F = JSON.parse(re.decode(y));
      } else F = y;
      if (F.asset === void 0 || F.asset.version[0] < 2) {
        T &&
          T(new Error("THREE.GLTFLoader: Unsupported asset. glTF versions >=2.0 are supported."));
        return;
      }
      const fe = new p(F, {
        path: b || this.resourcePath || "",
        crossOrigin: this.crossOrigin,
        requestHeader: this.requestHeader,
        manager: this.manager,
        ktx2Loader: this.ktx2Loader,
        meshoptDecoder: this.meshoptDecoder,
      });
      fe.fileLoader.setRequestHeader(this.requestHeader);
      for (let te = 0; te < this.pluginCallbacks.length; te++) {
        const Te = this.pluginCallbacks[te](fe);
        ((W[Te.name] = Te), (j[Te.name] = !0));
      }
      if (F.extensionsUsed)
        for (let te = 0; te < F.extensionsUsed.length; ++te) {
          const Te = F.extensionsUsed[te],
            Ge = F.extensionsRequired || [];
          switch (Te) {
            case ti.KHR_MATERIALS_UNLIT:
              j[Te] = new Xr();
              break;
            case ti.KHR_DRACO_MESH_COMPRESSION:
              j[Te] = new fl(F, this.dracoLoader);
              break;
            case ti.KHR_TEXTURE_TRANSFORM:
              j[Te] = new pl();
              break;
            case ti.KHR_MESH_QUANTIZATION:
              j[Te] = new ga();
              break;
            default:
              Ge.indexOf(Te) >= 0 &&
                W[Te] === void 0 &&
                console.warn('THREE.GLTFLoader: Unknown extension "' + Te + '".');
          }
        }
      ((F.additionalFiles = L), fe.setExtensions(j), fe.setPlugins(W), fe.parse(E, T));
    }
    parseAsync(y, b) {
      const E = this;
      return new Promise(function (T, L) {
        E.parse(y, b, T, L);
      });
    }
  }
  function Wl() {
    let ae = {};
    return {
      get: function (y) {
        return ae[y];
      },
      add: function (y, b) {
        ae[y] = b;
      },
      remove: function (y) {
        delete ae[y];
      },
      removeAll: function () {
        ae = {};
      },
    };
  }
  const ti = {
    KHR_BINARY_GLTF: "KHR_binary_glTF",
    KHR_DRACO_MESH_COMPRESSION: "KHR_draco_mesh_compression",
    KHR_LIGHTS_PUNCTUAL: "KHR_lights_punctual",
    KHR_MATERIALS_CLEARCOAT: "KHR_materials_clearcoat",
    KHR_MATERIALS_IOR: "KHR_materials_ior",
    KHR_MATERIALS_SHEEN: "KHR_materials_sheen",
    KHR_MATERIALS_SPECULAR: "KHR_materials_specular",
    KHR_MATERIALS_TRANSMISSION: "KHR_materials_transmission",
    KHR_MATERIALS_IRIDESCENCE: "KHR_materials_iridescence",
    KHR_MATERIALS_UNLIT: "KHR_materials_unlit",
    KHR_MATERIALS_VOLUME: "KHR_materials_volume",
    KHR_TEXTURE_BASISU: "KHR_texture_basisu",
    KHR_TEXTURE_TRANSFORM: "KHR_texture_transform",
    KHR_MESH_QUANTIZATION: "KHR_mesh_quantization",
    KHR_MATERIALS_EMISSIVE_STRENGTH: "KHR_materials_emissive_strength",
    EXT_TEXTURE_WEBP: "EXT_texture_webp",
    EXT_TEXTURE_AVIF: "EXT_texture_avif",
    EXT_MESHOPT_COMPRESSION: "EXT_meshopt_compression",
    EXT_MESH_GPU_INSTANCING: "EXT_mesh_gpu_instancing",
  };
  class jl {
    constructor(y) {
      ((this.parser = y),
        (this.name = ti.KHR_LIGHTS_PUNCTUAL),
        (this.cache = {
          refs: {},
          uses: {},
        }));
    }
    _markDefs() {
      const y = this.parser,
        b = this.parser.json.nodes || [];
      for (let E = 0, T = b.length; E < T; E++) {
        const L = b[E];
        L.extensions &&
          L.extensions[this.name] &&
          L.extensions[this.name].light !== void 0 &&
          y._addNodeRef(this.cache, L.extensions[this.name].light);
      }
    }
    _loadLight(y) {
      const b = this.parser,
        E = "light:" + y;
      let T = b.cache.get(E);
      if (T) return T;
      const L = b.json,
        W = (((L.extensions && L.extensions[this.name]) || {}).lights || [])[y];
      let re;
      const fe = new m.Ilk(16777215);
      W.color !== void 0 && fe.fromArray(W.color);
      const te = W.range !== void 0 ? W.range : 0;
      switch (W.type) {
        case "directional":
          ((re = new m.Ox3(fe)), re.target.position.set(0, 0, -1), re.add(re.target));
          break;
        case "point":
          ((re = new m.cek(fe)), (re.distance = te));
          break;
        case "spot":
          ((re = new m.PMe(fe)),
            (re.distance = te),
            (W.spot = W.spot || {}),
            (W.spot.innerConeAngle = W.spot.innerConeAngle !== void 0 ? W.spot.innerConeAngle : 0),
            (W.spot.outerConeAngle =
              W.spot.outerConeAngle !== void 0 ? W.spot.outerConeAngle : Math.PI / 4),
            (re.angle = W.spot.outerConeAngle),
            (re.penumbra = 1 - W.spot.innerConeAngle / W.spot.outerConeAngle),
            re.target.position.set(0, 0, -1),
            re.add(re.target));
          break;
        default:
          throw new Error("THREE.GLTFLoader: Unexpected light type: " + W.type);
      }
      return (
        re.position.set(0, 0, 0),
        (re.decay = 2),
        ns(re, W),
        W.intensity !== void 0 && (re.intensity = W.intensity),
        (re.name = b.createUniqueName(W.name || "light_" + y)),
        (T = Promise.resolve(re)),
        b.cache.add(E, T),
        T
      );
    }
    getDependency(y, b) {
      if (y === "light") return this._loadLight(b);
    }
    createNodeAttachment(y) {
      const b = this,
        E = this.parser,
        L = E.json.nodes[y],
        j = ((L.extensions && L.extensions[this.name]) || {}).light;
      return j === void 0
        ? null
        : this._loadLight(j).then(function (W) {
            return E._getNodeRef(b.cache, j, W);
          });
    }
  }
  class Xr {
    constructor() {
      this.name = ti.KHR_MATERIALS_UNLIT;
    }
    getMaterialType() {
      return m.vBJ;
    }
    extendParams(y, b, E) {
      const T = [];
      ((y.color = new m.Ilk(1, 1, 1)), (y.opacity = 1));
      const L = b.pbrMetallicRoughness;
      if (L) {
        if (Array.isArray(L.baseColorFactor)) {
          const F = L.baseColorFactor;
          (y.color.fromArray(F), (y.opacity = F[3]));
        }
        L.baseColorTexture !== void 0 &&
          T.push(E.assignTexture(y, "map", L.baseColorTexture, m.knz));
      }
      return Promise.all(T);
    }
  }
  class ol {
    constructor(y) {
      ((this.parser = y), (this.name = ti.KHR_MATERIALS_EMISSIVE_STRENGTH));
    }
    extendMaterialParams(y, b) {
      const T = this.parser.json.materials[y];
      if (!T.extensions || !T.extensions[this.name]) return Promise.resolve();
      const L = T.extensions[this.name].emissiveStrength;
      return (L !== void 0 && (b.emissiveIntensity = L), Promise.resolve());
    }
  }
  class al {
    constructor(y) {
      ((this.parser = y), (this.name = ti.KHR_MATERIALS_CLEARCOAT));
    }
    getMaterialType(y) {
      const E = this.parser.json.materials[y];
      return !E.extensions || !E.extensions[this.name] ? null : m.EJi;
    }
    extendMaterialParams(y, b) {
      const E = this.parser,
        T = E.json.materials[y];
      if (!T.extensions || !T.extensions[this.name]) return Promise.resolve();
      const L = [],
        F = T.extensions[this.name];
      if (
        (F.clearcoatFactor !== void 0 && (b.clearcoat = F.clearcoatFactor),
        F.clearcoatTexture !== void 0 &&
          L.push(E.assignTexture(b, "clearcoatMap", F.clearcoatTexture)),
        F.clearcoatRoughnessFactor !== void 0 &&
          (b.clearcoatRoughness = F.clearcoatRoughnessFactor),
        F.clearcoatRoughnessTexture !== void 0 &&
          L.push(E.assignTexture(b, "clearcoatRoughnessMap", F.clearcoatRoughnessTexture)),
        F.clearcoatNormalTexture !== void 0 &&
          (L.push(E.assignTexture(b, "clearcoatNormalMap", F.clearcoatNormalTexture)),
          F.clearcoatNormalTexture.scale !== void 0))
      ) {
        const j = F.clearcoatNormalTexture.scale;
        b.clearcoatNormalScale = new m.FM8(j, j);
      }
      return Promise.all(L);
    }
  }
  class $s {
    constructor(y) {
      ((this.parser = y), (this.name = ti.KHR_MATERIALS_IRIDESCENCE));
    }
    getMaterialType(y) {
      const E = this.parser.json.materials[y];
      return !E.extensions || !E.extensions[this.name] ? null : m.EJi;
    }
    extendMaterialParams(y, b) {
      const E = this.parser,
        T = E.json.materials[y];
      if (!T.extensions || !T.extensions[this.name]) return Promise.resolve();
      const L = [],
        F = T.extensions[this.name];
      return (
        F.iridescenceFactor !== void 0 && (b.iridescence = F.iridescenceFactor),
        F.iridescenceTexture !== void 0 &&
          L.push(E.assignTexture(b, "iridescenceMap", F.iridescenceTexture)),
        F.iridescenceIor !== void 0 && (b.iridescenceIOR = F.iridescenceIor),
        b.iridescenceThicknessRange === void 0 && (b.iridescenceThicknessRange = [100, 400]),
        F.iridescenceThicknessMinimum !== void 0 &&
          (b.iridescenceThicknessRange[0] = F.iridescenceThicknessMinimum),
        F.iridescenceThicknessMaximum !== void 0 &&
          (b.iridescenceThicknessRange[1] = F.iridescenceThicknessMaximum),
        F.iridescenceThicknessTexture !== void 0 &&
          L.push(E.assignTexture(b, "iridescenceThicknessMap", F.iridescenceThicknessTexture)),
        Promise.all(L)
      );
    }
  }
  class ho {
    constructor(y) {
      ((this.parser = y), (this.name = ti.KHR_MATERIALS_SHEEN));
    }
    getMaterialType(y) {
      const E = this.parser.json.materials[y];
      return !E.extensions || !E.extensions[this.name] ? null : m.EJi;
    }
    extendMaterialParams(y, b) {
      const E = this.parser,
        T = E.json.materials[y];
      if (!T.extensions || !T.extensions[this.name]) return Promise.resolve();
      const L = [];
      ((b.sheenColor = new m.Ilk(0, 0, 0)), (b.sheenRoughness = 0), (b.sheen = 1));
      const F = T.extensions[this.name];
      return (
        F.sheenColorFactor !== void 0 && b.sheenColor.fromArray(F.sheenColorFactor),
        F.sheenRoughnessFactor !== void 0 && (b.sheenRoughness = F.sheenRoughnessFactor),
        F.sheenColorTexture !== void 0 &&
          L.push(E.assignTexture(b, "sheenColorMap", F.sheenColorTexture, m.knz)),
        F.sheenRoughnessTexture !== void 0 &&
          L.push(E.assignTexture(b, "sheenRoughnessMap", F.sheenRoughnessTexture)),
        Promise.all(L)
      );
    }
  }
  class Xl {
    constructor(y) {
      ((this.parser = y), (this.name = ti.KHR_MATERIALS_TRANSMISSION));
    }
    getMaterialType(y) {
      const E = this.parser.json.materials[y];
      return !E.extensions || !E.extensions[this.name] ? null : m.EJi;
    }
    extendMaterialParams(y, b) {
      const E = this.parser,
        T = E.json.materials[y];
      if (!T.extensions || !T.extensions[this.name]) return Promise.resolve();
      const L = [],
        F = T.extensions[this.name];
      return (
        F.transmissionFactor !== void 0 && (b.transmission = F.transmissionFactor),
        F.transmissionTexture !== void 0 &&
          L.push(E.assignTexture(b, "transmissionMap", F.transmissionTexture)),
        Promise.all(L)
      );
    }
  }
  class ll {
    constructor(y) {
      ((this.parser = y), (this.name = ti.KHR_MATERIALS_VOLUME));
    }
    getMaterialType(y) {
      const E = this.parser.json.materials[y];
      return !E.extensions || !E.extensions[this.name] ? null : m.EJi;
    }
    extendMaterialParams(y, b) {
      const E = this.parser,
        T = E.json.materials[y];
      if (!T.extensions || !T.extensions[this.name]) return Promise.resolve();
      const L = [],
        F = T.extensions[this.name];
      ((b.thickness = F.thicknessFactor !== void 0 ? F.thicknessFactor : 0),
        F.thicknessTexture !== void 0 &&
          L.push(E.assignTexture(b, "thicknessMap", F.thicknessTexture)),
        (b.attenuationDistance = F.attenuationDistance || 1 / 0));
      const j = F.attenuationColor || [1, 1, 1];
      return ((b.attenuationColor = new m.Ilk(j[0], j[1], j[2])), Promise.all(L));
    }
  }
  class cl {
    constructor(y) {
      ((this.parser = y), (this.name = ti.KHR_MATERIALS_IOR));
    }
    getMaterialType(y) {
      const E = this.parser.json.materials[y];
      return !E.extensions || !E.extensions[this.name] ? null : m.EJi;
    }
    extendMaterialParams(y, b) {
      const T = this.parser.json.materials[y];
      if (!T.extensions || !T.extensions[this.name]) return Promise.resolve();
      const L = T.extensions[this.name];
      return ((b.ior = L.ior !== void 0 ? L.ior : 1.5), Promise.resolve());
    }
  }
  class fa {
    constructor(y) {
      ((this.parser = y), (this.name = ti.KHR_MATERIALS_SPECULAR));
    }
    getMaterialType(y) {
      const E = this.parser.json.materials[y];
      return !E.extensions || !E.extensions[this.name] ? null : m.EJi;
    }
    extendMaterialParams(y, b) {
      const E = this.parser,
        T = E.json.materials[y];
      if (!T.extensions || !T.extensions[this.name]) return Promise.resolve();
      const L = [],
        F = T.extensions[this.name];
      ((b.specularIntensity = F.specularFactor !== void 0 ? F.specularFactor : 1),
        F.specularTexture !== void 0 &&
          L.push(E.assignTexture(b, "specularIntensityMap", F.specularTexture)));
      const j = F.specularColorFactor || [1, 1, 1];
      return (
        (b.specularColor = new m.Ilk(j[0], j[1], j[2])),
        F.specularColorTexture !== void 0 &&
          L.push(E.assignTexture(b, "specularColorMap", F.specularColorTexture, m.knz)),
        Promise.all(L)
      );
    }
  }
  class ul {
    constructor(y) {
      ((this.parser = y), (this.name = ti.KHR_TEXTURE_BASISU));
    }
    loadTexture(y) {
      const b = this.parser,
        E = b.json,
        T = E.textures[y];
      if (!T.extensions || !T.extensions[this.name]) return null;
      const L = T.extensions[this.name],
        F = b.options.ktx2Loader;
      if (!F) {
        if (E.extensionsRequired && E.extensionsRequired.indexOf(this.name) >= 0)
          throw new Error(
            "THREE.GLTFLoader: setKTX2Loader must be called before loading KTX2 textures",
          );
        return null;
      }
      return b.loadTextureImage(y, L.source, F);
    }
  }
  class ka {
    constructor(y) {
      ((this.parser = y), (this.name = ti.EXT_TEXTURE_WEBP), (this.isSupported = null));
    }
    loadTexture(y) {
      const b = this.name,
        E = this.parser,
        T = E.json,
        L = T.textures[y];
      if (!L.extensions || !L.extensions[b]) return null;
      const F = L.extensions[b],
        j = T.images[F.source];
      let W = E.textureLoader;
      if (j.uri) {
        const re = E.options.manager.getHandler(j.uri);
        re !== null && (W = re);
      }
      return this.detectSupport().then(function (re) {
        if (re) return E.loadTextureImage(y, F.source, W);
        if (T.extensionsRequired && T.extensionsRequired.indexOf(b) >= 0)
          throw new Error("THREE.GLTFLoader: WebP required by asset but unsupported.");
        return E.loadTexture(y);
      });
    }
    detectSupport() {
      return (
        this.isSupported ||
          (this.isSupported = new Promise(function (y) {
            const b = new Image();
            ((b.src =
              "data:image/webp;base64,UklGRiIAAABXRUJQVlA4IBYAAAAwAQCdASoBAAEADsD+JaQAA3AAAAAA"),
              (b.onload = b.onerror =
                function () {
                  y(b.height === 1);
                }));
          })),
        this.isSupported
      );
    }
  }
  class Ua {
    constructor(y) {
      ((this.parser = y), (this.name = ti.EXT_TEXTURE_AVIF), (this.isSupported = null));
    }
    loadTexture(y) {
      const b = this.name,
        E = this.parser,
        T = E.json,
        L = T.textures[y];
      if (!L.extensions || !L.extensions[b]) return null;
      const F = L.extensions[b],
        j = T.images[F.source];
      let W = E.textureLoader;
      if (j.uri) {
        const re = E.options.manager.getHandler(j.uri);
        re !== null && (W = re);
      }
      return this.detectSupport().then(function (re) {
        if (re) return E.loadTextureImage(y, F.source, W);
        if (T.extensionsRequired && T.extensionsRequired.indexOf(b) >= 0)
          throw new Error("THREE.GLTFLoader: AVIF required by asset but unsupported.");
        return E.loadTexture(y);
      });
    }
    detectSupport() {
      return (
        this.isSupported ||
          (this.isSupported = new Promise(function (y) {
            const b = new Image();
            ((b.src =
              "data:image/avif;base64,AAAAIGZ0eXBhdmlmAAAAAGF2aWZtaWYxbWlhZk1BMUIAAADybWV0YQAAAAAAAAAoaGRscgAAAAAAAAAAcGljdAAAAAAAAAAAAAAAAGxpYmF2aWYAAAAADnBpdG0AAAAAAAEAAAAeaWxvYwAAAABEAAABAAEAAAABAAABGgAAABcAAAAoaWluZgAAAAAAAQAAABppbmZlAgAAAAABAABhdjAxQ29sb3IAAAAAamlwcnAAAABLaXBjbwAAABRpc3BlAAAAAAAAAAEAAAABAAAAEHBpeGkAAAAAAwgICAAAAAxhdjFDgQAMAAAAABNjb2xybmNseAACAAIABoAAAAAXaXBtYQAAAAAAAAABAAEEAQKDBAAAAB9tZGF0EgAKCBgABogQEDQgMgkQAAAAB8dSLfI="),
              (b.onload = b.onerror =
                function () {
                  y(b.height === 1);
                }));
          })),
        this.isSupported
      );
    }
  }
  class Na {
    constructor(y) {
      ((this.name = ti.EXT_MESHOPT_COMPRESSION), (this.parser = y));
    }
    loadBufferView(y) {
      const b = this.parser.json,
        E = b.bufferViews[y];
      if (E.extensions && E.extensions[this.name]) {
        const T = E.extensions[this.name],
          L = this.parser.getDependency("buffer", T.buffer),
          F = this.parser.options.meshoptDecoder;
        if (!F || !F.supported) {
          if (b.extensionsRequired && b.extensionsRequired.indexOf(this.name) >= 0)
            throw new Error(
              "THREE.GLTFLoader: setMeshoptDecoder must be called before loading compressed files",
            );
          return null;
        }
        return L.then(function (j) {
          const W = T.byteOffset || 0,
            re = T.byteLength || 0,
            fe = T.count,
            te = T.byteStride,
            Te = new Uint8Array(j, W, re);
          return F.decodeGltfBufferAsync
            ? F.decodeGltfBufferAsync(fe, te, Te, T.mode, T.filter).then(function (Ge) {
                return Ge.buffer;
              })
            : F.ready.then(function () {
                const Ge = new ArrayBuffer(fe * te);
                return (F.decodeGltfBuffer(new Uint8Array(Ge), fe, te, Te, T.mode, T.filter), Ge);
              });
        });
      } else return null;
    }
  }
  class pa {
    constructor(y) {
      ((this.name = ti.EXT_MESH_GPU_INSTANCING), (this.parser = y));
    }
    createNodeMesh(y) {
      const b = this.parser.json,
        E = b.nodes[y];
      if (!E.extensions || !E.extensions[this.name] || E.mesh === void 0) return null;
      const T = b.meshes[E.mesh];
      for (const re of T.primitives)
        if (
          re.mode !== Yr.TRIANGLES &&
          re.mode !== Yr.TRIANGLE_STRIP &&
          re.mode !== Yr.TRIANGLE_FAN &&
          re.mode !== void 0
        )
          return null;
      const F = E.extensions[this.name].attributes,
        j = [],
        W = {};
      for (const re in F)
        j.push(this.parser.getDependency("accessor", F[re]).then((fe) => ((W[re] = fe), W[re])));
      return j.length < 1
        ? null
        : (j.push(this.parser.createNodeMesh(y)),
          Promise.all(j).then((re) => {
            const fe = re.pop(),
              te = fe.isGroup ? fe.children : [fe],
              Te = re[0].count,
              Ge = [];
            for (const St of te) {
              const kt = new m.yGw(),
                Vt = new m.Pa4(),
                gt = new m._fP(),
                xt = new m.Pa4(1, 1, 1),
                Xe = new m.SPe(St.geometry, St.material, Te);
              for (let ut = 0; ut < Te; ut++)
                (W.TRANSLATION && Vt.fromBufferAttribute(W.TRANSLATION, ut),
                  W.ROTATION && gt.fromBufferAttribute(W.ROTATION, ut),
                  W.SCALE && xt.fromBufferAttribute(W.SCALE, ut),
                  Xe.setMatrixAt(ut, kt.compose(Vt, gt, xt)));
              for (const ut in W)
                ut !== "TRANSLATION" &&
                  ut !== "ROTATION" &&
                  ut !== "SCALE" &&
                  St.geometry.setAttribute(ut, W[ut]);
              (m.Tme.prototype.copy.call(Xe, St),
                (Xe.frustumCulled = !1),
                this.parser.assignFinalMaterial(Xe),
                Ge.push(Xe));
            }
            return fe.isGroup ? (fe.clear(), fe.add(...Ge), fe) : Ge[0];
          }));
    }
  }
  function hl(ae, y = 255) {
    for (let b = 0, E = ae.length; b < E; b++) ae[b] ^= y;
    return ae;
  }
  const za = "glTF",
    ma = "1031088470",
    nr = "152147171185",
    fo = 12,
    Ga = {
      JSON: 1313821514,
      BIN: 5130562,
    };
  class dl {
    constructor(y) {
      ((this.name = ti.KHR_BINARY_GLTF), (this.content = null), (this.body = null));
      const b = new DataView(y, 0, fo),
        E = new TextDecoder(),
        L = new Uint8Array(y, 0, 4).join("") === nr;
      if (
        ((this.header = {
          magic: za,
          version: b.getUint32(4, !0),
          length: b.getUint32(8, !0),
        }),
        this.header.magic !== za)
      )
        throw new Error("THREE.GLTFLoader: Unsupported glTF-Binary header.");
      if (this.header.version < 2)
        throw new Error("THREE.GLTFLoader: Legacy binary file detected.");
      const F = this.header.length - fo,
        j = new DataView(y, fo);
      let W = 0;
      for (; W < F;) {
        const re = j.getUint32(W, !0);
        ((W += 4), L && hl(new Uint8Array(y, fo + W, re + 4)));
        const fe = j.getUint32(W, !0);
        if (((W += 4), fe === Ga.JSON)) {
          const te = new Uint8Array(y, fo + W, re);
          this.content = E.decode(te);
        } else if (fe === Ga.BIN) {
          const te = fo + W;
          this.body = y.slice(te, te + re);
        }
        W += re;
      }
      if (this.content === null) throw new Error("THREE.GLTFLoader: JSON content not found.");
    }
  }
  class fl {
    constructor(y, b) {
      if (!b) throw new Error("THREE.GLTFLoader: No DRACOLoader instance provided.");
      ((this.name = ti.KHR_DRACO_MESH_COMPRESSION),
        (this.json = y),
        (this.dracoLoader = b),
        this.dracoLoader.preload());
    }
    decodePrimitive(y, b) {
      const E = this.json,
        T = this.dracoLoader,
        L = y.extensions[this.name].bufferView,
        F = y.extensions[this.name].attributes,
        j = {},
        W = {},
        re = {};
      for (const fe in F) {
        const te = Xo[fe] || fe.toLowerCase();
        j[te] = F[fe];
      }
      for (const fe in y.attributes) {
        const te = Xo[fe] || fe.toLowerCase();
        if (F[fe] !== void 0) {
          const Te = E.accessors[y.attributes[fe]],
            Ge = Qr[Te.componentType];
          ((re[te] = Ge.name), (W[te] = Te.normalized === !0));
        }
      }
      return b.getDependency("bufferView", L).then(function (fe) {
        return new Promise(function (te) {
          T.decodeDracoFile(
            fe,
            function (Te) {
              for (const Ge in Te.attributes) {
                const St = Te.attributes[Ge],
                  kt = W[Ge];
                kt !== void 0 && (St.normalized = kt);
              }
              te(Te);
            },
            j,
            re,
          );
        });
      });
    }
  }
  class pl {
    constructor() {
      this.name = ti.KHR_TEXTURE_TRANSFORM;
    }
    extendTexture(y, b) {
      return (
        b.texCoord !== void 0 &&
          console.warn(
            'THREE.GLTFLoader: Custom UV sets in "' + this.name + '" extension not yet supported.',
          ),
        (b.offset === void 0 && b.rotation === void 0 && b.scale === void 0) ||
          ((y = y.clone()),
          b.offset !== void 0 && y.offset.fromArray(b.offset),
          b.rotation !== void 0 && (y.rotation = b.rotation),
          b.scale !== void 0 && y.repeat.fromArray(b.scale),
          (y.needsUpdate = !0)),
        y
      );
    }
  }
  class ga {
    constructor() {
      this.name = ti.KHR_MESH_QUANTIZATION;
    }
  }
  class Ha extends m._C8 {
    constructor(y, b, E, T) {
      super(y, b, E, T);
    }
    copySampleValue_(y) {
      const b = this.resultBuffer,
        E = this.sampleValues,
        T = this.valueSize,
        L = y * T * 3 + T;
      for (let F = 0; F !== T; F++) b[F] = E[L + F];
      return b;
    }
    interpolate_(y, b, E, T) {
      const L = this.resultBuffer,
        F = this.sampleValues,
        j = this.valueSize,
        W = j * 2,
        re = j * 3,
        fe = T - b,
        te = (E - b) / fe,
        Te = te * te,
        Ge = Te * te,
        St = y * re,
        kt = St - re,
        Vt = -2 * Ge + 3 * Te,
        gt = Ge - Te,
        xt = 1 - Vt,
        Xe = gt - Te + te;
      for (let ut = 0; ut !== j; ut++) {
        const dn = F[kt + ut + j],
          qt = F[kt + ut + W] * fe,
          ln = F[St + ut + j],
          Tn = F[St + ut] * fe;
        L[ut] = xt * dn + Xe * qt + Vt * ln + gt * Tn;
      }
      return L;
    }
  }
  const To = new m._fP();
  class Eo extends Ha {
    interpolate_(y, b, E, T) {
      const L = super.interpolate_(y, b, E, T);
      return (To.fromArray(L).normalize().toArray(L), L);
    }
  }
  const Yr = {
      FLOAT: 5126,
      FLOAT_MAT3: 35675,
      FLOAT_MAT4: 35676,
      FLOAT_VEC2: 35664,
      FLOAT_VEC3: 35665,
      FLOAT_VEC4: 35666,
      LINEAR: 9729,
      REPEAT: 10497,
      SAMPLER_2D: 35678,
      POINTS: 0,
      LINES: 1,
      LINE_LOOP: 2,
      LINE_STRIP: 3,
      TRIANGLES: 4,
      TRIANGLE_STRIP: 5,
      TRIANGLE_FAN: 6,
      UNSIGNED_BYTE: 5121,
      UNSIGNED_SHORT: 5123,
    },
    Qr = {
      5120: Int8Array,
      5121: Uint8Array,
      5122: Int16Array,
      5123: Uint16Array,
      5125: Uint32Array,
      5126: Float32Array,
    },
    va = {
      9728: m.TyD,
      9729: m.wem,
      9984: m.YLQ,
      9985: m.qyh,
      9986: m.aH4,
      9987: m.D1R,
    },
    po = {
      33071: m.uWy,
      33648: m.OoA,
      10497: m.rpg,
    },
    Mo = {
      SCALAR: 1,
      VEC2: 2,
      VEC3: 3,
      VEC4: 4,
      MAT2: 4,
      MAT3: 9,
      MAT4: 16,
    },
    Xo = {
      POSITION: "position",
      NORMAL: "normal",
      TANGENT: "tangent",
      TEXCOORD_0: "uv",
      TEXCOORD_1: "uv2",
      COLOR_0: "color",
      WEIGHTS_0: "skinWeight",
      JOINTS_0: "skinIndex",
    },
    zs = {
      scale: "scale",
      translation: "position",
      rotation: "quaternion",
      weights: "morphTargetInfluences",
    },
    _a = {
      CUBICSPLINE: void 0,
      LINEAR: m.NMF,
      STEP: m.Syv,
    },
    Co = {
      OPAQUE: "OPAQUE",
      MASK: "MASK",
      BLEND: "BLEND",
    };
  function Va(ae) {
    return (
      ae.DefaultMaterial === void 0 &&
        (ae.DefaultMaterial = new m.Wid({
          color: 16777215,
          emissive: 0,
          metalness: 1,
          roughness: 1,
          transparent: !1,
          depthTest: !0,
          side: m.Wl3,
        })),
      ae.DefaultMaterial
    );
  }
  function eo(ae, y, b) {
    for (const E in b.extensions)
      ae[E] === void 0 &&
        ((y.userData.gltfExtensions = y.userData.gltfExtensions || {}),
        (y.userData.gltfExtensions[E] = b.extensions[E]));
  }
  function ns(ae, y) {
    y.extras !== void 0 &&
      (typeof y.extras == "object"
        ? Object.assign(ae.userData, y.extras)
        : console.warn("THREE.GLTFLoader: Ignoring primitive type .extras, " + y.extras));
  }
  function Po(ae, y, b) {
    let E = !1,
      T = !1,
      L = !1;
    for (let re = 0, fe = y.length; re < fe; re++) {
      const te = y[re];
      if (
        (te.POSITION !== void 0 && (E = !0),
        te.NORMAL !== void 0 && (T = !0),
        te.COLOR_0 !== void 0 && (L = !0),
        E && T && L)
      )
        break;
    }
    if (!E && !T && !L) return Promise.resolve(ae);
    const F = [],
      j = [],
      W = [];
    for (let re = 0, fe = y.length; re < fe; re++) {
      const te = y[re];
      if (E) {
        const Te =
          te.POSITION !== void 0
            ? b.getDependency("accessor", te.POSITION)
            : ae.attributes.position;
        F.push(Te);
      }
      if (T) {
        const Te =
          te.NORMAL !== void 0 ? b.getDependency("accessor", te.NORMAL) : ae.attributes.normal;
        j.push(Te);
      }
      if (L) {
        const Te =
          te.COLOR_0 !== void 0 ? b.getDependency("accessor", te.COLOR_0) : ae.attributes.color;
        W.push(Te);
      }
    }
    return Promise.all([Promise.all(F), Promise.all(j), Promise.all(W)]).then(function (re) {
      const fe = re[0],
        te = re[1],
        Te = re[2];
      return (
        E && (ae.morphAttributes.position = fe),
        T && (ae.morphAttributes.normal = te),
        L && (ae.morphAttributes.color = Te),
        (ae.morphTargetsRelative = !0),
        ae
      );
    });
  }
  function ya(ae, y) {
    if ((ae.updateMorphTargets(), y.weights !== void 0))
      for (let b = 0, E = y.weights.length; b < E; b++) ae.morphTargetInfluences[b] = y.weights[b];
    if (y.extras && Array.isArray(y.extras.targetNames)) {
      const b = y.extras.targetNames;
      if (ae.morphTargetInfluences.length === b.length) {
        ae.morphTargetDictionary = {};
        for (let E = 0, T = b.length; E < T; E++) ae.morphTargetDictionary[b[E]] = E;
      } else console.warn("THREE.GLTFLoader: Invalid extras.targetNames length. Ignoring names.");
    }
  }
  function Yo(ae) {
    const y = ae.extensions && ae.extensions[ti.KHR_DRACO_MESH_COMPRESSION];
    let b;
    return (
      y
        ? (b = "draco:" + y.bufferView + ":" + y.indices + ":" + mo(y.attributes))
        : (b = ae.indices + ":" + mo(ae.attributes) + ":" + ae.mode),
      b
    );
  }
  function mo(ae) {
    let y = "";
    const b = Object.keys(ae).sort();
    for (let E = 0, T = b.length; E < T; E++) y += b[E] + ":" + ae[b[E]] + ";";
    return y;
  }
  function ws(ae) {
    switch (ae) {
      case Int8Array:
        return 1 / 127;
      case Uint8Array:
        return 1 / 255;
      case Int16Array:
        return 1 / 32767;
      case Uint16Array:
        return 1 / 65535;
      default:
        throw new Error("THREE.GLTFLoader: Unsupported normalized accessor component type.");
    }
  }
  function Gs(ae) {
    return ae.search(/\.jpe?g($|\?)/i) > 0 || ae.search(/^data\:image\/jpeg/) === 0
      ? "image/jpeg"
      : ae.search(/\.webp($|\?)/i) > 0 || ae.search(/^data\:image\/webp/) === 0
        ? "image/webp"
        : "image/png";
  }
  const S = new m.yGw();
  class p {
    constructor(y = {}, b = {}) {
      ((this.json = y),
        (this.extensions = {}),
        (this.plugins = {}),
        (this.options = b),
        (this.cache = new Wl()),
        (this.associations = new Map()),
        (this.primitiveCache = {}),
        (this.nodeCache = {}),
        (this.meshCache = {
          refs: {},
          uses: {},
        }),
        (this.cameraCache = {
          refs: {},
          uses: {},
        }),
        (this.lightCache = {
          refs: {},
          uses: {},
        }),
        (this.sourceCache = {}),
        (this.textureCache = {}),
        (this.nodeNamesUsed = {}));
      let E = !1,
        T = !1,
        L = -1;
      (typeof navigator < "u" &&
        ((E = /^((?!chrome|android).)*safari/i.test(navigator.userAgent) === !0),
        (T = navigator.userAgent.indexOf("Firefox") > -1),
        (L = T ? navigator.userAgent.match(/Firefox\/([0-9]+)\./)[1] : -1)),
        typeof createImageBitmap > "u" || E || (T && L < 98)
          ? (this.textureLoader = new m.dpR(this.options.manager))
          : (this.textureLoader = new m.QRU(this.options.manager)),
        this.textureLoader.setCrossOrigin(this.options.crossOrigin),
        this.textureLoader.setRequestHeader(this.options.requestHeader),
        (this.fileLoader = new m.hH6(this.options.manager)),
        this.fileLoader.setResponseType("arraybuffer"),
        this.options.crossOrigin === "use-credentials" && this.fileLoader.setWithCredentials(!0));
    }
    setExtensions(y) {
      this.extensions = y;
    }
    setPlugins(y) {
      this.plugins = y;
    }
    parse(y, b) {
      const E = this,
        T = this.json,
        L = this.extensions;
      (this.cache.removeAll(),
        (this.nodeCache = {}),
        this._invokeAll(function (F) {
          return F._markDefs && F._markDefs();
        }),
        Promise.all(
          this._invokeAll(function (F) {
            return F.beforeRoot && F.beforeRoot();
          }),
        )
          .then(function () {
            return Promise.all([
              E.getDependencies("scene"),
              E.getDependencies("animation"),
              E.getDependencies("camera"),
            ]);
          })
          .then(function (F) {
            const j = {
              scene: F[0][T.scene || 0],
              scenes: F[0],
              animations: F[1],
              cameras: F[2],
              asset: T.asset,
              parser: E,
              userData: {},
            };
            (eo(L, j, T),
              ns(j, T),
              Promise.all(
                E._invokeAll(function (W) {
                  return W.afterRoot && W.afterRoot(j);
                }),
              ).then(function () {
                y(j);
              }));
          })
          .catch(b));
    }
    _markDefs() {
      const y = this.json.nodes || [],
        b = this.json.skins || [],
        E = this.json.meshes || [];
      for (let T = 0, L = b.length; T < L; T++) {
        const F = b[T].joints;
        for (let j = 0, W = F.length; j < W; j++) y[F[j]].isBone = !0;
      }
      for (let T = 0, L = y.length; T < L; T++) {
        const F = y[T];
        (F.mesh !== void 0 &&
          (this._addNodeRef(this.meshCache, F.mesh),
          F.skin !== void 0 && (E[F.mesh].isSkinnedMesh = !0)),
          F.camera !== void 0 && this._addNodeRef(this.cameraCache, F.camera));
      }
    }
    _addNodeRef(y, b) {
      b !== void 0 && (y.refs[b] === void 0 && (y.refs[b] = y.uses[b] = 0), y.refs[b]++);
    }
    _getNodeRef(y, b, E) {
      if (y.refs[b] <= 1) return E;
      const T = E.clone(),
        L = (F, j) => {
          const W = this.associations.get(F);
          W != null && this.associations.set(j, W);
          for (const [re, fe] of F.children.entries()) L(fe, j.children[re]);
        };
      return (L(E, T), (T.name += "_instance_" + y.uses[b]++), T);
    }
    _invokeOne(y) {
      const b = Object.values(this.plugins);
      b.push(this);
      for (let E = 0; E < b.length; E++) {
        const T = y(b[E]);
        if (T) return T;
      }
      return null;
    }
    _invokeAll(y) {
      const b = Object.values(this.plugins);
      b.unshift(this);
      const E = [];
      for (let T = 0; T < b.length; T++) {
        const L = y(b[T]);
        L && E.push(L);
      }
      return E;
    }
    getDependency(y, b) {
      const E = y + ":" + b;
      let T = this.cache.get(E);
      if (!T) {
        switch (y) {
          case "scene":
            T = this.loadScene(b);
            break;
          case "node":
            T = this._invokeOne(function (L) {
              return L.loadNode && L.loadNode(b);
            });
            break;
          case "mesh":
            T = this._invokeOne(function (L) {
              return L.loadMesh && L.loadMesh(b);
            });
            break;
          case "accessor":
            T = this.loadAccessor(b);
            break;
          case "bufferView":
            T = this._invokeOne(function (L) {
              return L.loadBufferView && L.loadBufferView(b);
            });
            break;
          case "buffer":
            T = this.loadBuffer(b);
            break;
          case "material":
            T = this._invokeOne(function (L) {
              return L.loadMaterial && L.loadMaterial(b);
            });
            break;
          case "texture":
            T = this._invokeOne(function (L) {
              return L.loadTexture && L.loadTexture(b);
            });
            break;
          case "skin":
            T = this.loadSkin(b);
            break;
          case "animation":
            T = this._invokeOne(function (L) {
              return L.loadAnimation && L.loadAnimation(b);
            });
            break;
          case "camera":
            T = this.loadCamera(b);
            break;
          default:
            if (
              ((T = this._invokeOne(function (L) {
                return L != this && L.getDependency && L.getDependency(y, b);
              })),
              !T)
            )
              throw new Error("Unknown type: " + y);
            break;
        }
        this.cache.add(E, T);
      }
      return T;
    }
    getDependencies(y) {
      let b = this.cache.get(y);
      if (!b) {
        const E = this,
          T = this.json[y + (y === "mesh" ? "es" : "s")] || [];
        ((b = Promise.all(
          T.map(function (L, F) {
            return E.getDependency(y, F);
          }),
        )),
          this.cache.add(y, b));
      }
      return b;
    }
    loadBuffer(y) {
      const b = this.json.buffers[y],
        E = this.fileLoader;
      if (b.type && b.type !== "arraybuffer")
        throw new Error("THREE.GLTFLoader: " + b.type + " buffer type is not supported.");
      if (b.uri === void 0 && y === 0)
        return Promise.resolve(this.extensions[ti.KHR_BINARY_GLTF].body);
      let T = this.json.additionalFiles,
        L = T ? T.find((j) => j.name === b.uri) : null;
      const F = this.options;
      return new Promise(function (j, W) {
        E.load(
          m.Zp0.resolveURL(b.uri, F.path),
          j,
          void 0,
          function () {
            W(new Error('THREE.GLTFLoader: Failed to load buffer "' + b.uri + '".'));
          },
          L,
        );
      });
    }
    loadBufferView(y) {
      const b = this.json.bufferViews[y];
      return this.getDependency("buffer", b.buffer).then(function (E) {
        const T = b.byteLength || 0,
          L = b.byteOffset || 0;
        return E.slice(L, L + T);
      });
    }
    loadAccessor(y) {
      const b = this,
        E = this.json,
        T = this.json.accessors[y];
      if (T.bufferView === void 0 && T.sparse === void 0) {
        const F = Mo[T.type],
          j = Qr[T.componentType],
          W = T.normalized === !0,
          re = new j(T.count * F);
        return Promise.resolve(new m.TlE(re, F, W));
      }
      const L = [];
      return (
        T.bufferView !== void 0
          ? L.push(this.getDependency("bufferView", T.bufferView))
          : L.push(null),
        T.sparse !== void 0 &&
          (L.push(this.getDependency("bufferView", T.sparse.indices.bufferView)),
          L.push(this.getDependency("bufferView", T.sparse.values.bufferView))),
        Promise.all(L).then(function (F) {
          const j = F[0],
            W = Mo[T.type],
            re = Qr[T.componentType],
            fe = re.BYTES_PER_ELEMENT,
            te = fe * W,
            Te = T.byteOffset || 0,
            Ge = T.bufferView !== void 0 ? E.bufferViews[T.bufferView].byteStride : void 0,
            St = T.normalized === !0;
          let kt, Vt;
          if (Ge && Ge !== te) {
            const gt = Math.floor(Te / Ge),
              xt =
                "InterleavedBuffer:" +
                T.bufferView +
                ":" +
                T.componentType +
                ":" +
                gt +
                ":" +
                T.count;
            let Xe = b.cache.get(xt);
            (Xe ||
              ((kt = new re(j, gt * Ge, (T.count * Ge) / fe)),
              (Xe = new m.vpT(kt, Ge / fe)),
              b.cache.add(xt, Xe)),
              (Vt = new m.kB5(Xe, W, (Te % Ge) / fe, St)));
          } else
            (j === null ? (kt = new re(T.count * W)) : (kt = new re(j, Te, T.count * W)),
              (Vt = new m.TlE(kt, W, St)));
          if (T.sparse !== void 0) {
            const gt = Mo.SCALAR,
              xt = Qr[T.sparse.indices.componentType],
              Xe = T.sparse.indices.byteOffset || 0,
              ut = T.sparse.values.byteOffset || 0,
              dn = new xt(F[1], Xe, T.sparse.count * gt),
              qt = new re(F[2], ut, T.sparse.count * W);
            j !== null && (Vt = new m.TlE(Vt.array.slice(), Vt.itemSize, Vt.normalized));
            for (let ln = 0, Tn = dn.length; ln < Tn; ln++) {
              const fn = dn[ln];
              if (
                (Vt.setX(fn, qt[ln * W]),
                W >= 2 && Vt.setY(fn, qt[ln * W + 1]),
                W >= 3 && Vt.setZ(fn, qt[ln * W + 2]),
                W >= 4 && Vt.setW(fn, qt[ln * W + 3]),
                W >= 5)
              )
                throw new Error(
                  "THREE.GLTFLoader: Unsupported itemSize in sparse BufferAttribute.",
                );
            }
          }
          return Vt;
        })
      );
    }
    loadTexture(y) {
      const b = this.json,
        E = this.options,
        L = b.textures[y].source,
        F = b.images[L];
      let j = this.textureLoader;
      if (F.uri) {
        const W = E.manager.getHandler(F.uri);
        W !== null && (j = W);
      }
      return this.loadTextureImage(y, L, j);
    }
    loadTextureImage(y, b, E) {
      const T = this,
        L = this.json,
        F = L.textures[y],
        j = L.images[b],
        W = (j.uri || j.bufferView) + ":" + F.sampler;
      if (this.textureCache[W]) return this.textureCache[W];
      const re = this.loadImageSource(b, E)
        .then(function (fe) {
          ((fe.flipY = !1), (fe.name = F.name || j.name || ""));
          const Te = (L.samplers || {})[F.sampler] || {};
          return (
            (fe.magFilter = va[Te.magFilter] || m.wem),
            (fe.minFilter = va[Te.minFilter] || m.D1R),
            (fe.wrapS = po[Te.wrapS] || m.rpg),
            (fe.wrapT = po[Te.wrapT] || m.rpg),
            T.associations.set(fe, {
              textures: y,
            }),
            fe
          );
        })
        .catch(function () {
          return null;
        });
      return ((this.textureCache[W] = re), re);
    }
    loadImageSource(y, b) {
      const E = this,
        T = this.json,
        L = this.options;
      if (this.sourceCache[y] !== void 0) return this.sourceCache[y].then((te) => te.clone());
      const F = T.images[y],
        j = self.URL || self.webkitURL;
      let W = F.uri || "",
        re = !1;
      if (F.bufferView !== void 0)
        W = E.getDependency("bufferView", F.bufferView).then(function (te) {
          re = !0;
          const Te = new Blob([te], {
            type: F.mimeType,
          });
          return ((W = j.createObjectURL(Te)), W);
        });
      else {
        if (F.uri === void 0)
          throw new Error("THREE.GLTFLoader: Image " + y + " is missing URI and bufferView");
        if (T.additionalFiles) {
          let te = W.split("\\").pop().split("/").pop(),
            Te = T.additionalFiles.find((Ge) => te === Ge.name);
          Te && (W = (0, Js.hR)(Te));
        }
      }
      const fe = Promise.resolve(W)
        .then(function (te) {
          return new Promise(function (Te, Ge) {
            let St = Te;
            (b.isImageBitmapLoader === !0 &&
              (St = function (kt) {
                const Vt = new m.xEZ(kt);
                ((Vt.needsUpdate = !0), Te(Vt));
              }),
              b.load(m.Zp0.resolveURL(te, L.path), St, void 0, Ge));
          });
        })
        .then(function (te) {
          return (
            re === !0 && j.revokeObjectURL(W),
            (te.userData.mimeType = F.mimeType || Gs(F.uri)),
            te
          );
        })
        .catch(function (te) {
          throw (console.error("THREE.GLTFLoader: Couldn't load texture", W), te);
        });
      return ((this.sourceCache[y] = fe), fe);
    }
    assignTexture(y, b, E, T) {
      const L = this;
      return this.getDependency("texture", E.index).then(function (F) {
        if (!F) return null;
        if (
          (E.texCoord !== void 0 &&
            E.texCoord != 0 &&
            !(b === "aoMap" && E.texCoord == 1) &&
            console.warn(
              "THREE.GLTFLoader: Custom UV set " +
                E.texCoord +
                " for texture " +
                b +
                " not yet supported.",
            ),
          L.extensions[ti.KHR_TEXTURE_TRANSFORM])
        ) {
          const j = E.extensions !== void 0 ? E.extensions[ti.KHR_TEXTURE_TRANSFORM] : void 0;
          if (j) {
            const W = L.associations.get(F);
            ((F = L.extensions[ti.KHR_TEXTURE_TRANSFORM].extendTexture(F, j)),
              L.associations.set(F, W));
          }
        }
        return (T !== void 0 && (F.encoding = T), (y[b] = F), F);
      });
    }
    assignFinalMaterial(y) {
      const b = y.geometry;
      let E = y.material;
      const T = b.attributes.tangent === void 0,
        L = b.attributes.color !== void 0,
        F = b.attributes.normal === void 0;
      if (y.isPoints) {
        const j = "PointsMaterial:" + E.uuid;
        let W = this.cache.get(j);
        (W ||
          ((W = new m.UY4()),
          m.F5T.prototype.copy.call(W, E),
          W.color.copy(E.color),
          (W.map = E.map),
          (W.sizeAttenuation = !1),
          this.cache.add(j, W)),
          (E = W));
      } else if (y.isLine) {
        const j = "LineBasicMaterial:" + E.uuid;
        let W = this.cache.get(j);
        (W ||
          ((W = new m.nls()),
          m.F5T.prototype.copy.call(W, E),
          W.color.copy(E.color),
          this.cache.add(j, W)),
          (E = W));
      }
      if (T || L || F) {
        let j = "ClonedMaterial:" + E.uuid + ":";
        (T && (j += "derivative-tangents:"),
          L && (j += "vertex-colors:"),
          F && (j += "flat-shading:"));
        let W = this.cache.get(j);
        (W ||
          ((W = E.clone()),
          L && (W.vertexColors = !0),
          F && (W.flatShading = !0),
          T &&
            (W.normalScale && (W.normalScale.y *= -1),
            W.clearcoatNormalScale && (W.clearcoatNormalScale.y *= -1)),
          this.cache.add(j, W),
          this.associations.set(W, this.associations.get(E))),
          (E = W));
      }
      (E.aoMap &&
        b.attributes.uv2 === void 0 &&
        b.attributes.uv !== void 0 &&
        b.setAttribute("uv2", b.attributes.uv),
        (y.material = E));
    }
    getMaterialType() {
      return m.Wid;
    }
    loadMaterial(y) {
      const b = this,
        E = this.json,
        T = this.extensions,
        L = E.materials[y];
      let F;
      const j = {},
        W = L.extensions || {},
        re = [];
      if (W[ti.KHR_MATERIALS_UNLIT]) {
        const te = T[ti.KHR_MATERIALS_UNLIT];
        ((F = te.getMaterialType()), re.push(te.extendParams(j, L, b)));
      } else {
        const te = L.pbrMetallicRoughness || {};
        if (((j.color = new m.Ilk(1, 1, 1)), (j.opacity = 1), Array.isArray(te.baseColorFactor))) {
          const Te = te.baseColorFactor;
          (j.color.fromArray(Te), (j.opacity = Te[3]));
        }
        (te.baseColorTexture !== void 0 &&
          re.push(b.assignTexture(j, "map", te.baseColorTexture, m.knz)),
          (j.metalness = te.metallicFactor !== void 0 ? te.metallicFactor : 1),
          (j.roughness = te.roughnessFactor !== void 0 ? te.roughnessFactor : 1),
          te.metallicRoughnessTexture !== void 0 &&
            (re.push(b.assignTexture(j, "metalnessMap", te.metallicRoughnessTexture)),
            re.push(b.assignTexture(j, "roughnessMap", te.metallicRoughnessTexture))),
          (F = this._invokeOne(function (Te) {
            return Te.getMaterialType && Te.getMaterialType(y);
          })),
          re.push(
            Promise.all(
              this._invokeAll(function (Te) {
                return Te.extendMaterialParams && Te.extendMaterialParams(y, j);
              }),
            ),
          ));
      }
      L.doubleSided === !0 && (j.side = m.ehD);
      const fe = L.alphaMode || Co.OPAQUE;
      if (
        (fe === Co.BLEND
          ? ((j.transparent = !0), (j.depthWrite = !1))
          : ((j.transparent = !1),
            fe === Co.MASK && (j.alphaTest = L.alphaCutoff !== void 0 ? L.alphaCutoff : 0.5)),
        L.normalTexture !== void 0 &&
          F !== m.vBJ &&
          (re.push(b.assignTexture(j, "normalMap", L.normalTexture)),
          (j.normalScale = new m.FM8(1, 1)),
          L.normalTexture.scale !== void 0))
      ) {
        const te = L.normalTexture.scale;
        j.normalScale.set(te, te);
      }
      return (
        L.occlusionTexture !== void 0 &&
          F !== m.vBJ &&
          (re.push(b.assignTexture(j, "aoMap", L.occlusionTexture)),
          L.occlusionTexture.strength !== void 0 &&
            (j.aoMapIntensity = L.occlusionTexture.strength)),
        L.emissiveFactor !== void 0 &&
          F !== m.vBJ &&
          (j.emissive = new m.Ilk().fromArray(L.emissiveFactor)),
        L.emissiveTexture !== void 0 &&
          F !== m.vBJ &&
          re.push(b.assignTexture(j, "emissiveMap", L.emissiveTexture, m.knz)),
        Promise.all(re).then(function () {
          const te = new F(j);
          return (
            L.name && (te.name = L.name),
            ns(te, L),
            b.associations.set(te, {
              materials: y,
            }),
            L.extensions && eo(T, te, L),
            te
          );
        })
      );
    }
    createUniqueName(y) {
      const b = m.iUV.sanitizeNodeName(y || "");
      let E = b;
      for (let T = 1; this.nodeNamesUsed[E]; ++T) E = b + "_" + T;
      return ((this.nodeNamesUsed[E] = !0), E);
    }
    loadGeometries(y) {
      const b = this,
        E = this.extensions,
        T = this.primitiveCache;
      function L(j) {
        return E[ti.KHR_DRACO_MESH_COMPRESSION].decodePrimitive(j, b).then(function (W) {
          return V(W, j, b);
        });
      }
      const F = [];
      for (let j = 0, W = y.length; j < W; j++) {
        const re = y[j],
          fe = Yo(re),
          te = T[fe];
        if (te) F.push(te.promise);
        else {
          let Te;
          (re.extensions && re.extensions[ti.KHR_DRACO_MESH_COMPRESSION]
            ? (Te = L(re))
            : (Te = V(new m.u9r(), re, b)),
            (T[fe] = {
              primitive: re,
              promise: Te,
            }),
            F.push(Te));
        }
      }
      return Promise.all(F);
    }
    loadMesh(y) {
      const b = this,
        E = this.json,
        T = this.extensions,
        L = E.meshes[y],
        F = L.primitives,
        j = [];
      for (let W = 0, re = F.length; W < re; W++) {
        const fe =
          F[W].material === void 0 ? Va(this.cache) : this.getDependency("material", F[W].material);
        j.push(fe);
      }
      return (
        j.push(b.loadGeometries(F)),
        Promise.all(j).then(function (W) {
          const re = W.slice(0, W.length - 1),
            fe = W[W.length - 1],
            te = [];
          for (let Ge = 0, St = fe.length; Ge < St; Ge++) {
            const kt = fe[Ge],
              Vt = F[Ge];
            let gt;
            const xt = re[Ge];
            if (
              Vt.mode === Yr.TRIANGLES ||
              Vt.mode === Yr.TRIANGLE_STRIP ||
              Vt.mode === Yr.TRIANGLE_FAN ||
              Vt.mode === void 0
            )
              ((gt = L.isSkinnedMesh === !0 ? new m.TUv(kt, xt) : new m.Kj0(kt, xt)),
                gt.isSkinnedMesh === !0 && gt.normalizeSkinWeights(),
                Vt.mode === Yr.TRIANGLE_STRIP
                  ? (gt.geometry = So(gt.geometry, m.UlW))
                  : Vt.mode === Yr.TRIANGLE_FAN && (gt.geometry = So(gt.geometry, m.z$h)));
            else if (Vt.mode === Yr.LINES) gt = new m.ejS(kt, xt);
            else if (Vt.mode === Yr.LINE_STRIP) gt = new m.x12(kt, xt);
            else if (Vt.mode === Yr.LINE_LOOP) gt = new m.blk(kt, xt);
            else if (Vt.mode === Yr.POINTS) gt = new m.woe(kt, xt);
            else throw new Error("THREE.GLTFLoader: Primitive mode unsupported: " + Vt.mode);
            (Object.keys(gt.geometry.morphAttributes).length > 0 && ya(gt, L),
              (gt.name = b.createUniqueName(L.name || "mesh_" + y)),
              ns(gt, L),
              Vt.extensions && eo(T, gt, Vt),
              b.assignFinalMaterial(gt),
              te.push(gt));
          }
          for (let Ge = 0, St = te.length; Ge < St; Ge++)
            b.associations.set(te[Ge], {
              meshes: y,
              primitives: Ge,
            });
          if (te.length === 1) return te[0];
          const Te = new m.ZAu();
          b.associations.set(Te, {
            meshes: y,
          });
          for (let Ge = 0, St = te.length; Ge < St; Ge++) Te.add(te[Ge]);
          return Te;
        })
      );
    }
    loadCamera(y) {
      let b;
      const E = this.json.cameras[y],
        T = E[E.type];
      if (!T) {
        console.warn("THREE.GLTFLoader: Missing camera parameters.");
        return;
      }
      return (
        E.type === "perspective"
          ? (b = new m.cPb(m.M8C.radToDeg(T.yfov), T.aspectRatio || 1, T.znear || 1, T.zfar || 2e6))
          : E.type === "orthographic" &&
            (b = new m.iKG(-T.xmag, T.xmag, T.ymag, -T.ymag, T.znear, T.zfar)),
        E.name && (b.name = this.createUniqueName(E.name)),
        ns(b, E),
        Promise.resolve(b)
      );
    }
    loadSkin(y) {
      const b = this.json.skins[y],
        E = [];
      for (let T = 0, L = b.joints.length; T < L; T++) E.push(this._loadNodeShallow(b.joints[T]));
      return (
        b.inverseBindMatrices !== void 0
          ? E.push(this.getDependency("accessor", b.inverseBindMatrices))
          : E.push(null),
        Promise.all(E).then(function (T) {
          const L = T.pop(),
            F = T,
            j = [],
            W = [];
          for (let re = 0, fe = F.length; re < fe; re++) {
            const te = F[re];
            if (te) {
              j.push(te);
              const Te = new m.yGw();
              (L !== null && Te.fromArray(L.array, re * 16), W.push(Te));
            } else console.warn('THREE.GLTFLoader: Joint "%s" could not be found.', b.joints[re]);
          }
          return new m.OdW(j, W);
        })
      );
    }
    loadAnimation(y) {
      const E = this.json.animations[y],
        T = [],
        L = [],
        F = [],
        j = [],
        W = [];
      for (let re = 0, fe = E.channels.length; re < fe; re++) {
        const te = E.channels[re],
          Te = E.samplers[te.sampler],
          Ge = te.target,
          St = Ge.node,
          kt = E.parameters !== void 0 ? E.parameters[Te.input] : Te.input,
          Vt = E.parameters !== void 0 ? E.parameters[Te.output] : Te.output;
        (T.push(this.getDependency("node", St)),
          L.push(this.getDependency("accessor", kt)),
          F.push(this.getDependency("accessor", Vt)),
          j.push(Te),
          W.push(Ge));
      }
      return Promise.all([
        Promise.all(T),
        Promise.all(L),
        Promise.all(F),
        Promise.all(j),
        Promise.all(W),
      ]).then(function (re) {
        const fe = re[0],
          te = re[1],
          Te = re[2],
          Ge = re[3],
          St = re[4],
          kt = [];
        for (let gt = 0, xt = fe.length; gt < xt; gt++) {
          const Xe = fe[gt],
            ut = te[gt],
            dn = Te[gt],
            qt = Ge[gt],
            ln = St[gt];
          if (Xe === void 0) continue;
          Xe.updateMatrix();
          let Tn;
          switch (zs[ln.path]) {
            case zs.weights:
              Tn = m.dUE;
              break;
            case zs.rotation:
              Tn = m.iLg;
              break;
            case zs.position:
            case zs.scale:
            default:
              Tn = m.yC1;
              break;
          }
          const fn = Xe.name ? Xe.name : Xe.uuid,
            Hn = qt.interpolation !== void 0 ? _a[qt.interpolation] : m.NMF,
            En = [];
          zs[ln.path] === zs.weights
            ? Xe.traverse(function (ar) {
                ar.morphTargetInfluences && En.push(ar.name ? ar.name : ar.uuid);
              })
            : En.push(fn);
          let Ei = dn.array;
          if (dn.normalized) {
            const ar = ws(Ei.constructor),
              fr = new Float32Array(Ei.length);
            for (let lr = 0, is = Ei.length; lr < is; lr++) fr[lr] = Ei[lr] * ar;
            Ei = fr;
          }
          for (let ar = 0, fr = En.length; ar < fr; ar++) {
            const lr = new Tn(En[ar] + "." + zs[ln.path], ut.array, Ei, Hn);
            (qt.interpolation === "CUBICSPLINE" &&
              ((lr.createInterpolant = function (Tr) {
                const Er = this instanceof m.iLg ? Eo : Ha;
                return new Er(this.times, this.values, this.getValueSize() / 3, Tr);
              }),
              (lr.createInterpolant.isInterpolantFactoryMethodGLTFCubicSpline = !0)),
              kt.push(lr));
          }
        }
        const Vt = E.name ? E.name : "animation_" + y;
        return new m.m7l(Vt, void 0, kt);
      });
    }
    createNodeMesh(y) {
      const b = this.json,
        E = this,
        T = b.nodes[y];
      return T.mesh === void 0
        ? null
        : E.getDependency("mesh", T.mesh).then(function (L) {
            const F = E._getNodeRef(E.meshCache, T.mesh, L);
            return (
              T.weights !== void 0 &&
                F.traverse(function (j) {
                  if (j.isMesh)
                    for (let W = 0, re = T.weights.length; W < re; W++)
                      j.morphTargetInfluences[W] = T.weights[W];
                }),
              F
            );
          });
    }
    loadNode(y) {
      const b = this.json,
        E = this,
        T = b.nodes[y],
        L = E._loadNodeShallow(y),
        F = [],
        j = T.children || [];
      for (let re = 0, fe = j.length; re < fe; re++) F.push(E.getDependency("node", j[re]));
      const W = T.skin === void 0 ? Promise.resolve(null) : E.getDependency("skin", T.skin);
      return Promise.all([L, Promise.all(F), W]).then(function (re) {
        const fe = re[0],
          te = re[1],
          Te = re[2];
        Te !== null &&
          fe.traverse(function (Ge) {
            Ge.isSkinnedMesh && Ge.bind(Te, S);
          });
        for (let Ge = 0, St = te.length; Ge < St; Ge++) fe.add(te[Ge]);
        return fe;
      });
    }
    _loadNodeShallow(y) {
      const b = this.json,
        E = this.extensions,
        T = this;
      if (this.nodeCache[y] !== void 0) return this.nodeCache[y];
      const L = b.nodes[y],
        F = L.name ? T.createUniqueName(L.name) : "",
        j = [],
        W = T._invokeOne(function (re) {
          return re.createNodeMesh && re.createNodeMesh(y);
        });
      return (
        W && j.push(W),
        L.camera !== void 0 &&
          j.push(
            T.getDependency("camera", L.camera).then(function (re) {
              return T._getNodeRef(T.cameraCache, L.camera, re);
            }),
          ),
        T._invokeAll(function (re) {
          return re.createNodeAttachment && re.createNodeAttachment(y);
        }).forEach(function (re) {
          j.push(re);
        }),
        (this.nodeCache[y] = Promise.all(j).then(function (re) {
          let fe;
          if (
            (L.isBone === !0
              ? (fe = new m.N$j())
              : re.length > 1
                ? (fe = new m.ZAu())
                : re.length === 1
                  ? (fe = re[0])
                  : (fe = new m.Tme()),
            fe !== re[0])
          )
            for (let te = 0, Te = re.length; te < Te; te++) fe.add(re[te]);
          if (
            (L.name && ((fe.userData.name = L.name), (fe.name = F)),
            ns(fe, L),
            L.extensions && eo(E, fe, L),
            L.matrix !== void 0)
          ) {
            const te = new m.yGw();
            (te.fromArray(L.matrix), fe.applyMatrix4(te));
          } else
            (L.translation !== void 0 && fe.position.fromArray(L.translation),
              L.rotation !== void 0 && fe.quaternion.fromArray(L.rotation),
              L.scale !== void 0 && fe.scale.fromArray(L.scale));
          return (
            T.associations.has(fe) || T.associations.set(fe, {}),
            (T.associations.get(fe).nodes = y),
            fe
          );
        })),
        this.nodeCache[y]
      );
    }
    loadScene(y) {
      const b = this.extensions,
        E = this.json.scenes[y],
        T = this,
        L = new m.ZAu();
      (E.name && (L.name = T.createUniqueName(E.name)), ns(L, E), E.extensions && eo(b, L, E));
      const F = E.nodes || [],
        j = [];
      for (let W = 0, re = F.length; W < re; W++) j.push(T.getDependency("node", F[W]));
      return Promise.all(j).then(function (W) {
        for (let fe = 0, te = W.length; fe < te; fe++) L.add(W[fe]);
        const re = (fe) => {
          const te = new Map();
          for (const [Te, Ge] of T.associations)
            (Te instanceof m.F5T || Te instanceof m.xEZ) && te.set(Te, Ge);
          return (
            fe.traverse((Te) => {
              const Ge = T.associations.get(Te);
              Ge != null && te.set(Te, Ge);
            }),
            te
          );
        };
        return ((T.associations = re(L)), L);
      });
    }
  }
  function C(ae, y, b) {
    const E = y.attributes,
      T = new m.ZzF();
    if (E.POSITION !== void 0) {
      const j = b.json.accessors[E.POSITION],
        W = j.min,
        re = j.max;
      if (W !== void 0 && re !== void 0) {
        if ((T.set(new m.Pa4(W[0], W[1], W[2]), new m.Pa4(re[0], re[1], re[2])), j.normalized)) {
          const fe = ws(Qr[j.componentType]);
          (T.min.multiplyScalar(fe), T.max.multiplyScalar(fe));
        }
      } else {
        console.warn("THREE.GLTFLoader: Missing min/max properties for accessor POSITION.");
        return;
      }
    } else return;
    const L = y.targets;
    if (L !== void 0) {
      const j = new m.Pa4(),
        W = new m.Pa4();
      for (let re = 0, fe = L.length; re < fe; re++) {
        const te = L[re];
        if (te.POSITION !== void 0) {
          const Te = b.json.accessors[te.POSITION],
            Ge = Te.min,
            St = Te.max;
          if (Ge !== void 0 && St !== void 0) {
            if (
              (W.setX(Math.max(Math.abs(Ge[0]), Math.abs(St[0]))),
              W.setY(Math.max(Math.abs(Ge[1]), Math.abs(St[1]))),
              W.setZ(Math.max(Math.abs(Ge[2]), Math.abs(St[2]))),
              Te.normalized)
            ) {
              const kt = ws(Qr[Te.componentType]);
              W.multiplyScalar(kt);
            }
            j.max(W);
          } else
            console.warn("THREE.GLTFLoader: Missing min/max properties for accessor POSITION.");
        }
      }
      T.expandByVector(j);
    }
    ae.boundingBox = T;
    const F = new m.aLr();
    (T.getCenter(F.center), (F.radius = T.min.distanceTo(T.max) / 2), (ae.boundingSphere = F));
  }
  function V(ae, y, b) {
    const E = y.attributes,
      T = [];
    function L(F, j) {
      return b.getDependency("accessor", F).then(function (W) {
        ae.setAttribute(j, W);
      });
    }
    for (const F in E) {
      const j = Xo[F] || F.toLowerCase();
      j in ae.attributes || T.push(L(E[F], j));
    }
    if (y.indices !== void 0 && !ae.index) {
      const F = b.getDependency("accessor", y.indices).then(function (j) {
        ae.setIndex(j);
      });
      T.push(F);
    }
    return (
      ns(ae, y),
      C(ae, y, b),
      Promise.all(T).then(function () {
        return y.targets !== void 0 ? Po(ae, y.targets, b) : ae;
      })
    );
  }
  var se = (function () {
    var ae =
        "b9H79Tebbbe8Fv9Gbb9Gvuuuuueu9Giuuub9Geueu9Giuuueuikqbeeedddillviebeoweuec:q;iekr;leDo9TW9T9VV95dbH9F9F939H79T9F9J9H229F9Jt9VV7bb8A9TW79O9V9Wt9F9KW9J9V9KW9wWVtW949c919M9MWVbeY9TW79O9V9Wt9F9KW9J9V9KW69U9KW949c919M9MWVbdE9TW79O9V9Wt9F9KW9J9V9KW69U9KW949tWG91W9U9JWbiL9TW79O9V9Wt9F9KW9J9V9KWS9P2tWV9p9JtblK9TW79O9V9Wt9F9KW9J9V9KWS9P2tWV9r919HtbvL9TW79O9V9Wt9F9KW9J9V9KWS9P2tWVT949Wbol79IV9Rbrq:P8Yqdbk;3sezu8Jjjjjbcj;eb9Rgv8Kjjjjbc9:hodnadcefal0mbcuhoaiRbbc:Ge9hmbavaialfgrad9Radz1jjjbhwcj;abad9UhoaicefhldnadTmbaoc;WFbGgocjdaocjd6EhDcbhqinaqae9pmeaDaeaq9RaqaDfae6Egkcsfgocl4cifcd4hxdndndndnaoc9WGgmTmbcbhPcehsawcjdfhzalhHinaraH9Rax6midnaraHaxfgl9RcK6mbczhoinawcj;cbfaogifgoc9WfhOdndndndndnaHaic9WfgAco4fRbbaAci4coG4ciGPlbedibkaO9cb83ibaOcwf9cb83ibxikaOalRblalRbbgAco4gCaCciSgCE86bbaocGfalclfaCfgORbbaAcl4ciGgCaCciSgCE86bbaocVfaOaCfgORbbaAcd4ciGgCaCciSgCE86bbaoc7faOaCfgORbbaAciGgAaAciSgAE86bbaoctfaOaAfgARbbalRbegOco4gCaCciSgCE86bbaoc91faAaCfgARbbaOcl4ciGgCaCciSgCE86bbaoc4faAaCfgARbbaOcd4ciGgCaCciSgCE86bbaoc93faAaCfgARbbaOciGgOaOciSgOE86bbaoc94faAaOfgARbbalRbdgOco4gCaCciSgCE86bbaoc95faAaCfgARbbaOcl4ciGgCaCciSgCE86bbaoc96faAaCfgARbbaOcd4ciGgCaCciSgCE86bbaoc97faAaCfgARbbaOciGgOaOciSgOE86bbaoc98faAaOfgORbbalRbiglco4gAaAciSgAE86bbaoc99faOaAfgORbbalcl4ciGgAaAciSgAE86bbaoc9:faOaAfgORbbalcd4ciGgAaAciSgAE86bbaocufaOaAfgoRbbalciGglalciSglE86bbaoalfhlxdkaOalRbwalRbbgAcl4gCaCcsSgCE86bbaocGfalcwfaCfgORbbaAcsGgAaAcsSgAE86bbaocVfaOaAfgORbbalRbegAcl4gCaCcsSgCE86bbaoc7faOaCfgORbbaAcsGgAaAcsSgAE86bbaoctfaOaAfgORbbalRbdgAcl4gCaCcsSgCE86bbaoc91faOaCfgORbbaAcsGgAaAcsSgAE86bbaoc4faOaAfgORbbalRbigAcl4gCaCcsSgCE86bbaoc93faOaCfgORbbaAcsGgAaAcsSgAE86bbaoc94faOaAfgORbbalRblgAcl4gCaCcsSgCE86bbaoc95faOaCfgORbbaAcsGgAaAcsSgAE86bbaoc96faOaAfgORbbalRbvgAcl4gCaCcsSgCE86bbaoc97faOaCfgORbbaAcsGgAaAcsSgAE86bbaoc98faOaAfgORbbalRbogAcl4gCaCcsSgCE86bbaoc99faOaCfgORbbaAcsGgAaAcsSgAE86bbaoc9:faOaAfgORbbalRbrglcl4gAaAcsSgAE86bbaocufaOaAfgoRbbalcsGglalcsSglE86bbaoalfhlxekaOal8Pbb83bbaOcwfalcwf8Pbb83bbalczfhlkdnaiam9pmbaiczfhoaral9RcL0mekkaiam6mialTmidnakTmbawaPfRbbhOcbhoazhiinaiawcj;cbfaofRbbgAce4cbaAceG9R7aOfgO86bbaiadfhiaocefgoak9hmbkkazcefhzaPcefgPad6hsalhHaPad9hmexvkkcbhlasceGmdxikalaxad2fhCdnakTmbcbhHcehsawcjdfhminaral9Rax6mialTmdalaxfhlawaHfRbbhOcbhoamhiinaiawcj;cbfaofRbbgAce4cbaAceG9R7aOfgO86bbaiadfhiaocefgoak9hmbkamcefhmaHcefgHad6hsaHad9hmbkaChlxikcbhocehsinaral9Rax6mdalTmealaxfhlaocefgoad6hsadao9hmbkaChlxdkcbhlasceGTmekc9:hoxikabaqad2fawcjdfakad2z1jjjb8Aawawcjdfakcufad2fadz1jjjb8Aakaqfhqalmbkc9:hoxekcbc99aral9Radcaadca0ESEhokavcj;ebf8Kjjjjbaok;yzeHu8Jjjjjbc;ae9Rgv8Kjjjjbc9:hodnaeci9UgrcHfal0mbcuhoaiRbbgwc;WeGc;Ge9hmbawcsGgDce0mbavc;abfcFecjez:jjjjb8AavcUf9cu83ibavc8Wf9cu83ibavcyf9cu83ibavcaf9cu83ibavcKf9cu83ibavczf9cu83ibav9cu83iwav9cu83ibaialfc9WfhqaicefgwarfhodnaeTmbcmcsaDceSEhkcbhxcbhmcbhDcbhicbhlindnaoaq9nmbc9:hoxikdndnawRbbgrc;Ve0mbavc;abfalarcl4cu7fcsGcitfgPydlhsaPydbhzdnarcsGgPak9pmbavaiarcu7fcsGcdtfydbaxaPEhraPThPdndnadcd9hmbabaDcetfgHaz87ebaHcdfas87ebaHclfar87ebxekabaDcdtfgHazBdbaHclfasBdbaHcwfarBdbkaxaPfhxavc;abfalcitfgHarBdbaHasBdlavaicdtfarBdbavc;abfalcefcsGglcitfgHazBdbaHarBdlaiaPfhialcefhlxdkdndnaPcsSmbamaPfaPc987fcefhmxekaocefhrao8SbbgPcFeGhHdndnaPcu9mmbarhoxekaocvfhoaHcFbGhHcrhPdninar8SbbgOcFbGaPtaHVhHaOcu9kmearcefhraPcrfgPc8J9hmbxdkkarcefhokaHce4cbaHceG9R7amfhmkdndnadcd9hmbabaDcetfgraz87ebarcdfas87ebarclfam87ebxekabaDcdtfgrazBdbarclfasBdbarcwfamBdbkavc;abfalcitfgramBdbarasBdlavaicdtfamBdbavc;abfalcefcsGglcitfgrazBdbaramBdlaicefhialcefhlxekdnarcpe0mbaxcefgOavaiaqarcsGfRbbgPcl49RcsGcdtfydbaPcz6gHEhravaiaP9RcsGcdtfydbaOaHfgsaPcsGgOEhPaOThOdndnadcd9hmbabaDcetfgzax87ebazcdfar87ebazclfaP87ebxekabaDcdtfgzaxBdbazclfarBdbazcwfaPBdbkavaicdtfaxBdbavc;abfalcitfgzarBdbazaxBdlavaicefgicsGcdtfarBdbavc;abfalcefcsGcitfgzaPBdbazarBdlavaiaHfcsGgicdtfaPBdbavc;abfalcdfcsGglcitfgraxBdbaraPBdlalcefhlaiaOfhiasaOfhxxekaxcbaoRbbgzEgAarc;:eSgrfhsazcsGhCazcl4hXdndnazcs0mbascefhOxekashOavaiaX9RcsGcdtfydbhskdndnaCmbaOcefhxxekaOhxavaiaz9RcsGcdtfydbhOkdndnarTmbaocefhrxekaocdfhrao8SbegHcFeGhPdnaHcu9kmbaocofhAaPcFbGhPcrhodninar8SbbgHcFbGaotaPVhPaHcu9kmearcefhraocrfgoc8J9hmbkaAhrxekarcefhrkaPce4cbaPceG9R7amfgmhAkdndnaXcsSmbarhPxekarcefhPar8SbbgocFeGhHdnaocu9kmbarcvfhsaHcFbGhHcrhodninaP8SbbgrcFbGaotaHVhHarcu9kmeaPcefhPaocrfgoc8J9hmbkashPxekaPcefhPkaHce4cbaHceG9R7amfgmhskdndnaCcsSmbaPhoxekaPcefhoaP8SbbgrcFeGhHdnarcu9kmbaPcvfhOaHcFbGhHcrhrdninao8SbbgPcFbGartaHVhHaPcu9kmeaocefhoarcrfgrc8J9hmbkaOhoxekaocefhokaHce4cbaHceG9R7amfgmhOkdndnadcd9hmbabaDcetfgraA87ebarcdfas87ebarclfaO87ebxekabaDcdtfgraABdbarclfasBdbarcwfaOBdbkavc;abfalcitfgrasBdbaraABdlavaicdtfaABdbavc;abfalcefcsGcitfgraOBdbarasBdlavaicefgicsGcdtfasBdbavc;abfalcdfcsGcitfgraABdbaraOBdlavaiazcz6aXcsSVfgicsGcdtfaOBdbaiaCTaCcsSVfhialcifhlkawcefhwalcsGhlaicsGhiaDcifgDae6mbkkcbc99aoaqSEhokavc;aef8Kjjjjbaok:llevu8Jjjjjbcz9Rhvc9:hodnaecvfal0mbcuhoaiRbbc;:eGc;qe9hmbav9cb83iwaicefhraialfc98fhwdnaeTmbdnadcdSmbcbhDindnaraw6mbc9:skarcefhoar8SbbglcFeGhidndnalcu9mmbaohrxekarcvfhraicFbGhicrhldninao8SbbgdcFbGaltaiVhiadcu9kmeaocefhoalcrfglc8J9hmbxdkkaocefhrkabaDcdtfaicd4cbaice4ceG9R7avcwfaiceGcdtVgoydbfglBdbaoalBdbaDcefgDae9hmbxdkkcbhDindnaraw6mbc9:skarcefhoar8SbbglcFeGhidndnalcu9mmbaohrxekarcvfhraicFbGhicrhldninao8SbbgdcFbGaltaiVhiadcu9kmeaocefhoalcrfglc8J9hmbxdkkaocefhrkabaDcetfaicd4cbaice4ceG9R7avcwfaiceGcdtVgoydbfgl87ebaoalBdbaDcefgDae9hmbkkcbc99arawSEhokaok:Lvoeue99dud99eud99dndnadcl9hmbaeTmeindndnabcdfgd8Sbb:Yab8Sbbgi:Ygl:l:tabcefgv8Sbbgo:Ygr:l:tgwJbb;:9cawawNJbbbbawawJbbbb9GgDEgq:mgkaqaicb9iEalMgwawNakaqaocb9iEarMgqaqNMM:r:vglNJbbbZJbbb:;aDEMgr:lJbbb9p9DTmbar:Ohixekcjjjj94hikadai86bbdndnaqalNJbbbZJbbb:;aqJbbbb9GEMgq:lJbbb9p9DTmbaq:Ohdxekcjjjj94hdkavad86bbdndnawalNJbbbZJbbb:;awJbbbb9GEMgw:lJbbb9p9DTmbaw:Ohdxekcjjjj94hdkabad86bbabclfhbaecufgembxdkkaeTmbindndnabclfgd8Ueb:Yab8Uebgi:Ygl:l:tabcdfgv8Uebgo:Ygr:l:tgwJb;:FSawawNJbbbbawawJbbbb9GgDEgq:mgkaqaicb9iEalMgwawNakaqaocb9iEarMgqaqNMM:r:vglNJbbbZJbbb:;aDEMgr:lJbbb9p9DTmbar:Ohixekcjjjj94hikadai87ebdndnaqalNJbbbZJbbb:;aqJbbbb9GEMgq:lJbbb9p9DTmbaq:Ohdxekcjjjj94hdkavad87ebdndnawalNJbbbZJbbb:;awJbbbb9GEMgw:lJbbb9p9DTmbaw:Ohdxekcjjjj94hdkabad87ebabcwfhbaecufgembkkk;siliui99iue99dnaeTmbcbhiabhlindndnJ;Zl81Zalcof8UebgvciV:Y:vgoal8Ueb:YNgrJb;:FSNJbbbZJbbb:;arJbbbb9GEMgw:lJbbb9p9DTmbaw:OhDxekcjjjj94hDkalclf8Uebhqalcdf8UebhkabavcefciGaiVcetfaD87ebdndnaoak:YNgwJb;:FSNJbbbZJbbb:;awJbbbb9GEMgx:lJbbb9p9DTmbax:Ohkxekcjjjj94hkkabavcdfciGaiVcetfak87ebdndnaoaq:YNgoJb;:FSNJbbbZJbbb:;aoJbbbb9GEMgx:lJbbb9p9DTmbax:Ohqxekcjjjj94hqkabavcufciGaiVcetfaq87ebdndnJbbjZararN:tawawN:taoaoN:tgrJbbbbarJbbbb9GE:rJb;:FSNJbbbZMgr:lJbbb9p9DTmbar:Ohqxekcjjjj94hqkabavciGaiVcetfaq87ebalcwfhlaiclfhiaecufgembkkk9mbdnadcd4ae2geTmbinababydbgdcwtcw91:Yadce91cjjj;8ifcjjj98G::NUdbabclfhbaecufgembkkk9teiucbcbydj1jjbgeabcifc98GfgbBdj1jjbdndnabZbcztgd9nmbcuhiabad9RcFFifcz4nbcuSmekaehikaik;LeeeudndnaeabVciGTmbabhixekdndnadcz9pmbabhixekabhiinaiaeydbBdbaiclfaeclfydbBdbaicwfaecwfydbBdbaicxfaecxfydbBdbaiczfhiaeczfheadc9Wfgdcs0mbkkadcl6mbinaiaeydbBdbaeclfheaiclfhiadc98fgdci0mbkkdnadTmbinaiaeRbb86bbaicefhiaecefheadcufgdmbkkabk;aeedudndnabciGTmbabhixekaecFeGc:b:c:ew2hldndnadcz9pmbabhixekabhiinaialBdbaicxfalBdbaicwfalBdbaiclfalBdbaiczfhiadc9Wfgdcs0mbkkadcl6mbinaialBdbaiclfhiadc98fgdci0mbkkdnadTmbinaiae86bbaicefhiadcufgdmbkkabkkkebcjwklz9Kbb",
      y =
        "b9H79TebbbeKl9Gbb9Gvuuuuueu9Giuuub9Geueuikqbbebeedddilve9Weeeviebeoweuec:q;Aekr;leDo9TW9T9VV95dbH9F9F939H79T9F9J9H229F9Jt9VV7bb8A9TW79O9V9Wt9F9KW9J9V9KW9wWVtW949c919M9MWVbdY9TW79O9V9Wt9F9KW9J9V9KW69U9KW949c919M9MWVblE9TW79O9V9Wt9F9KW9J9V9KW69U9KW949tWG91W9U9JWbvL9TW79O9V9Wt9F9KW9J9V9KWS9P2tWV9p9JtboK9TW79O9V9Wt9F9KW9J9V9KWS9P2tWV9r919HtbrL9TW79O9V9Wt9F9KW9J9V9KWS9P2tWVT949Wbwl79IV9RbDq;t9tqlbzik9:evu8Jjjjjbcz9Rhbcbheincbhdcbhiinabcwfadfaicjuaead4ceGglE86bbaialfhiadcefgdcw9hmbkaec:q:yjjbfai86bbaecitc:q1jjbfab8Piw83ibaecefgecjd9hmbkk;h8JlHud97euo978Jjjjjbcj;kb9Rgv8Kjjjjbc9:hodnadcefal0mbcuhoaiRbbc:Ge9hmbavaialfgrad9Rad;8qbbcj;abad9UhoaicefhldnadTmbaoc;WFbGgocjdaocjd6EhwcbhDinaDae9pmeawaeaD9RaDawfae6Egqcsfgoc9WGgkci2hxakcethmaocl4cifcd4hPabaDad2fhscbhzdnincehHalhOcbhAdninaraO9RaP6miavcj;cbfaAak2fhCaOaPfhlcbhidnakc;ab6mbaral9Rc;Gb6mbcbhoinaCaofhidndndndndnaOaoco4fRbbgXciGPlbedibkaipxbbbbbbbbbbbbbbbbpklbxikaialpbblalpbbbgQclp:meaQpmbzeHdOiAlCvXoQrLgQcdp:meaQpmbzeHdOiAlCvXoQrLpxiiiiiiiiiiiiiiiip9ogLpxiiiiiiiiiiiiiiiip8JgQp5b9cjF;8;4;W;G;ab9:9cU1:NgKcitc:q1jjbfpbibaKc:q:yjjbfpbbbgYaYpmbbbbbbbbbbbbbbbbaQp5e9cjF;8;4;W;G;ab9:9cU1:NgKcitc:q1jjbfpbibp9UpmbedilvorzHOACXQLpPaLaQp9spklbalclfaYpQbfaKc:q:yjjbfRbbfhlxdkaialpbbwalpbbbgQclp:meaQpmbzeHdOiAlCvXoQrLpxssssssssssssssssp9ogLpxssssssssssssssssp8JgQp5b9cjF;8;4;W;G;ab9:9cU1:NgKcitc:q1jjbfpbibaKc:q:yjjbfpbbbgYaYpmbbbbbbbbbbbbbbbbaQp5e9cjF;8;4;W;G;ab9:9cU1:NgKcitc:q1jjbfpbibp9UpmbedilvorzHOACXQLpPaLaQp9spklbalcwfaYpQbfaKc:q:yjjbfRbbfhlxekaialpbbbpklbalczfhlkdndndndndnaXcd4ciGPlbedibkaipxbbbbbbbbbbbbbbbbpklzxikaialpbblalpbbbgQclp:meaQpmbzeHdOiAlCvXoQrLgQcdp:meaQpmbzeHdOiAlCvXoQrLpxiiiiiiiiiiiiiiiip9ogLpxiiiiiiiiiiiiiiiip8JgQp5b9cjF;8;4;W;G;ab9:9cU1:NgKcitc:q1jjbfpbibaKc:q:yjjbfpbbbgYaYpmbbbbbbbbbbbbbbbbaQp5e9cjF;8;4;W;G;ab9:9cU1:NgKcitc:q1jjbfpbibp9UpmbedilvorzHOACXQLpPaLaQp9spklzalclfaYpQbfaKc:q:yjjbfRbbfhlxdkaialpbbwalpbbbgQclp:meaQpmbzeHdOiAlCvXoQrLpxssssssssssssssssp9ogLpxssssssssssssssssp8JgQp5b9cjF;8;4;W;G;ab9:9cU1:NgKcitc:q1jjbfpbibaKc:q:yjjbfpbbbgYaYpmbbbbbbbbbbbbbbbbaQp5e9cjF;8;4;W;G;ab9:9cU1:NgKcitc:q1jjbfpbibp9UpmbedilvorzHOACXQLpPaLaQp9spklzalcwfaYpQbfaKc:q:yjjbfRbbfhlxekaialpbbbpklzalczfhlkdndndndndnaXcl4ciGPlbedibkaipxbbbbbbbbbbbbbbbbpklaxikaialpbblalpbbbgQclp:meaQpmbzeHdOiAlCvXoQrLgQcdp:meaQpmbzeHdOiAlCvXoQrLpxiiiiiiiiiiiiiiiip9ogLpxiiiiiiiiiiiiiiiip8JgQp5b9cjF;8;4;W;G;ab9:9cU1:NgKcitc:q1jjbfpbibaKc:q:yjjbfpbbbgYaYpmbbbbbbbbbbbbbbbbaQp5e9cjF;8;4;W;G;ab9:9cU1:NgKcitc:q1jjbfpbibp9UpmbedilvorzHOACXQLpPaLaQp9spklaalclfaYpQbfaKc:q:yjjbfRbbfhlxdkaialpbbwalpbbbgQclp:meaQpmbzeHdOiAlCvXoQrLpxssssssssssssssssp9ogLpxssssssssssssssssp8JgQp5b9cjF;8;4;W;G;ab9:9cU1:NgKcitc:q1jjbfpbibaKc:q:yjjbfpbbbgYaYpmbbbbbbbbbbbbbbbbaQp5e9cjF;8;4;W;G;ab9:9cU1:NgKcitc:q1jjbfpbibp9UpmbedilvorzHOACXQLpPaLaQp9spklaalcwfaYpQbfaKc:q:yjjbfRbbfhlxekaialpbbbpklaalczfhlkdndndndndnaXco4Plbedibkaipxbbbbbbbbbbbbbbbbpkl8WxikaialpbblalpbbbgQclp:meaQpmbzeHdOiAlCvXoQrLgQcdp:meaQpmbzeHdOiAlCvXoQrLpxiiiiiiiiiiiiiiiip9ogLpxiiiiiiiiiiiiiiiip8JgQp5b9cjF;8;4;W;G;ab9:9cU1:NgXcitc:q1jjbfpbibaXc:q:yjjbfpbbbgYaYpmbbbbbbbbbbbbbbbbaQp5e9cjF;8;4;W;G;ab9:9cU1:NgXcitc:q1jjbfpbibp9UpmbedilvorzHOACXQLpPaLaQp9spkl8WalclfaYpQbfaXc:q:yjjbfRbbfhlxdkaialpbbwalpbbbgQclp:meaQpmbzeHdOiAlCvXoQrLpxssssssssssssssssp9ogLpxssssssssssssssssp8JgQp5b9cjF;8;4;W;G;ab9:9cU1:NgXcitc:q1jjbfpbibaXc:q:yjjbfpbbbgYaYpmbbbbbbbbbbbbbbbbaQp5e9cjF;8;4;W;G;ab9:9cU1:NgXcitc:q1jjbfpbibp9UpmbedilvorzHOACXQLpPaLaQp9spkl8WalcwfaYpQbfaXc:q:yjjbfRbbfhlxekaialpbbbpkl8Walczfhlkaoc;abfhiaocjefak0meaihoaral9Rc;Fb0mbkkdndnaiak9pmbaici4hoinaral9RcK6mdaCaifhXdndndndndnaOaico4fRbbaocoG4ciGPlbedibkaXpxbbbbbbbbbbbbbbbbpklbxikaXalpbblalpbbbgQclp:meaQpmbzeHdOiAlCvXoQrLgQcdp:meaQpmbzeHdOiAlCvXoQrLpxiiiiiiiiiiiiiiiip9ogLpxiiiiiiiiiiiiiiiip8JgQp5b9cjF;8;4;W;G;ab9:9cU1:NgKcitc:q1jjbfpbibaKc:q:yjjbfpbbbgYaYpmbbbbbbbbbbbbbbbbaQp5e9cjF;8;4;W;G;ab9:9cU1:NgKcitc:q1jjbfpbibp9UpmbedilvorzHOACXQLpPaLaQp9spklbalclfaYpQbfaKc:q:yjjbfRbbfhlxdkaXalpbbwalpbbbgQclp:meaQpmbzeHdOiAlCvXoQrLpxssssssssssssssssp9ogLpxssssssssssssssssp8JgQp5b9cjF;8;4;W;G;ab9:9cU1:NgKcitc:q1jjbfpbibaKc:q:yjjbfpbbbgYaYpmbbbbbbbbbbbbbbbbaQp5e9cjF;8;4;W;G;ab9:9cU1:NgKcitc:q1jjbfpbibp9UpmbedilvorzHOACXQLpPaLaQp9spklbalcwfaYpQbfaKc:q:yjjbfRbbfhlxekaXalpbbbpklbalczfhlkaocdfhoaiczfgiak6mbkkalTmbaAci6hHalhOaAcefgohAaoclSmdxekkcbhlaHceGmdkdnakTmbavcjdfazfhiavazfpbdbhYcbhXinaiavcj;cbfaXfgopblbgLcep9TaLpxeeeeeeeeeeeeeeeegQp9op9Hp9rgLaoakfpblbg8Acep9Ta8AaQp9op9Hp9rg8ApmbzeHdOiAlCvXoQrLgEaoamfpblbg3cep9Ta3aQp9op9Hp9rg3aoaxfpblbg5cep9Ta5aQp9op9Hp9rg5pmbzeHdOiAlCvXoQrLg8EpmbezHdiOAlvCXorQLgQaQpmbedibedibedibediaYp9UgYp9AdbbaiadfgoaYaQaQpmlvorlvorlvorlvorp9UgYp9AdbbaoadfgoaYaQaQpmwDqkwDqkwDqkwDqkp9UgYp9AdbbaoadfgoaYaQaQpmxmPsxmPsxmPsxmPsp9UgYp9AdbbaoadfgoaYaEa8EpmwDKYqk8AExm35Ps8E8FgQaQpmbedibedibedibedip9UgYp9AdbbaoadfgoaYaQaQpmlvorlvorlvorlvorp9UgYp9AdbbaoadfgoaYaQaQpmwDqkwDqkwDqkwDqkp9UgYp9AdbbaoadfgoaYaQaQpmxmPsxmPsxmPsxmPsp9UgYp9AdbbaoadfgoaYaLa8ApmwKDYq8AkEx3m5P8Es8FgLa3a5pmwKDYq8AkEx3m5P8Es8Fg8ApmbezHdiOAlvCXorQLgQaQpmbedibedibedibedip9UgYp9AdbbaoadfgoaYaQaQpmlvorlvorlvorlvorp9UgYp9AdbbaoadfgoaYaQaQpmwDqkwDqkwDqkwDqkp9UgYp9AdbbaoadfgoaYaQaQpmxmPsxmPsxmPsxmPsp9UgYp9AdbbaoadfgoaYaLa8ApmwDKYqk8AExm35Ps8E8FgQaQpmbedibedibedibedip9UgYp9AdbbaoadfgoaYaQaQpmlvorlvorlvorlvorp9UgYp9AdbbaoadfgoaYaQaQpmwDqkwDqkwDqkwDqkp9UgYp9AdbbaoadfgoaYaQaQpmxmPsxmPsxmPsxmPsp9UgYp9AdbbaoadfhiaXczfgXak6mbkkazclfgzad6mbkasavcjdfaqad2;8qbbavavcjdfaqcufad2fad;8qbbaqaDfhDc9:hoalmexikkc9:hoxekcbc99aral9Radcaadca0ESEhokavcj;kbf8Kjjjjbaokwbz:bjjjbk;uzeHu8Jjjjjbc;ae9Rgv8Kjjjjbc9:hodnaeci9UgrcHfal0mbcuhoaiRbbgwc;WeGc;Ge9hmbawcsGgDce0mbavc;abfcFecje;8kbavcUf9cu83ibavc8Wf9cu83ibavcyf9cu83ibavcaf9cu83ibavcKf9cu83ibavczf9cu83ibav9cu83iwav9cu83ibaialfc9WfhqaicefgwarfhodnaeTmbcmcsaDceSEhkcbhxcbhmcbhDcbhicbhlindnaoaq9nmbc9:hoxikdndnawRbbgrc;Ve0mbavc;abfalarcl4cu7fcsGcitfgPydlhsaPydbhzdnarcsGgPak9pmbavaiarcu7fcsGcdtfydbaxaPEhraPThPdndnadcd9hmbabaDcetfgHaz87ebaHcdfas87ebaHclfar87ebxekabaDcdtfgHazBdbaHclfasBdbaHcwfarBdbkaxaPfhxavc;abfalcitfgHarBdbaHasBdlavaicdtfarBdbavc;abfalcefcsGglcitfgHazBdbaHarBdlaiaPfhialcefhlxdkdndnaPcsSmbamaPfaPc987fcefhmxekaocefhrao8SbbgPcFeGhHdndnaPcu9mmbarhoxekaocvfhoaHcFbGhHcrhPdninar8SbbgOcFbGaPtaHVhHaOcu9kmearcefhraPcrfgPc8J9hmbxdkkarcefhokaHce4cbaHceG9R7amfhmkdndnadcd9hmbabaDcetfgraz87ebarcdfas87ebarclfam87ebxekabaDcdtfgrazBdbarclfasBdbarcwfamBdbkavc;abfalcitfgramBdbarasBdlavaicdtfamBdbavc;abfalcefcsGglcitfgrazBdbaramBdlaicefhialcefhlxekdnarcpe0mbaxcefgOavaiaqarcsGfRbbgPcl49RcsGcdtfydbaPcz6gHEhravaiaP9RcsGcdtfydbaOaHfgsaPcsGgOEhPaOThOdndnadcd9hmbabaDcetfgzax87ebazcdfar87ebazclfaP87ebxekabaDcdtfgzaxBdbazclfarBdbazcwfaPBdbkavaicdtfaxBdbavc;abfalcitfgzarBdbazaxBdlavaicefgicsGcdtfarBdbavc;abfalcefcsGcitfgzaPBdbazarBdlavaiaHfcsGgicdtfaPBdbavc;abfalcdfcsGglcitfgraxBdbaraPBdlalcefhlaiaOfhiasaOfhxxekaxcbaoRbbgzEgAarc;:eSgrfhsazcsGhCazcl4hXdndnazcs0mbascefhOxekashOavaiaX9RcsGcdtfydbhskdndnaCmbaOcefhxxekaOhxavaiaz9RcsGcdtfydbhOkdndnarTmbaocefhrxekaocdfhrao8SbegHcFeGhPdnaHcu9kmbaocofhAaPcFbGhPcrhodninar8SbbgHcFbGaotaPVhPaHcu9kmearcefhraocrfgoc8J9hmbkaAhrxekarcefhrkaPce4cbaPceG9R7amfgmhAkdndnaXcsSmbarhPxekarcefhPar8SbbgocFeGhHdnaocu9kmbarcvfhsaHcFbGhHcrhodninaP8SbbgrcFbGaotaHVhHarcu9kmeaPcefhPaocrfgoc8J9hmbkashPxekaPcefhPkaHce4cbaHceG9R7amfgmhskdndnaCcsSmbaPhoxekaPcefhoaP8SbbgrcFeGhHdnarcu9kmbaPcvfhOaHcFbGhHcrhrdninao8SbbgPcFbGartaHVhHaPcu9kmeaocefhoarcrfgrc8J9hmbkaOhoxekaocefhokaHce4cbaHceG9R7amfgmhOkdndnadcd9hmbabaDcetfgraA87ebarcdfas87ebarclfaO87ebxekabaDcdtfgraABdbarclfasBdbarcwfaOBdbkavc;abfalcitfgrasBdbaraABdlavaicdtfaABdbavc;abfalcefcsGcitfgraOBdbarasBdlavaicefgicsGcdtfasBdbavc;abfalcdfcsGcitfgraABdbaraOBdlavaiazcz6aXcsSVfgicsGcdtfaOBdbaiaCTaCcsSVfhialcifhlkawcefhwalcsGhlaicsGhiaDcifgDae6mbkkcbc99aoaqSEhokavc;aef8Kjjjjbaok:llevu8Jjjjjbcz9Rhvc9:hodnaecvfal0mbcuhoaiRbbc;:eGc;qe9hmbav9cb83iwaicefhraialfc98fhwdnaeTmbdnadcdSmbcbhDindnaraw6mbc9:skarcefhoar8SbbglcFeGhidndnalcu9mmbaohrxekarcvfhraicFbGhicrhldninao8SbbgdcFbGaltaiVhiadcu9kmeaocefhoalcrfglc8J9hmbxdkkaocefhrkabaDcdtfaicd4cbaice4ceG9R7avcwfaiceGcdtVgoydbfglBdbaoalBdbaDcefgDae9hmbxdkkcbhDindnaraw6mbc9:skarcefhoar8SbbglcFeGhidndnalcu9mmbaohrxekarcvfhraicFbGhicrhldninao8SbbgdcFbGaltaiVhiadcu9kmeaocefhoalcrfglc8J9hmbxdkkaocefhrkabaDcetfaicd4cbaice4ceG9R7avcwfaiceGcdtVgoydbfgl87ebaoalBdbaDcefgDae9hmbkkcbc99arawSEhokaok:EPliuo97eue978Jjjjjbca9Rhidndnadcl9hmbdnaec98GglTmbcbhvabhdinadadpbbbgocKp:RecKp:Sep;6egraocwp:RecKp:Sep;6earp;Geaoczp:RecKp:Sep;6egwp;Gep;Kep;LegDpxbbbbbbbbbbbbbbbbp:2egqarpxbbbjbbbjbbbjbbbjgkp9op9rp;Kegrpxbb;:9cbb;:9cbb;:9cbb;:9cararp;MeaDaDp;Meawaqawakp9op9rp;Kegrarp;Mep;Kep;Kep;Jep;Negwp;Mepxbbn0bbn0bbn0bbn0gqp;KepxFbbbFbbbFbbbFbbbp9oaopxbbbFbbbFbbbFbbbFp9op9qarawp;Meaqp;Kecwp:RepxbFbbbFbbbFbbbFbbp9op9qaDawp;Meaqp;Keczp:RepxbbFbbbFbbbFbbbFbp9op9qpkbbadczfhdavclfgval6mbkkalae9pmeaiaeciGgvcdtgdVcbczad9R;8kbaiabalcdtfglad;8qbbdnavTmbaiaipblbgocKp:RecKp:Sep;6egraocwp:RecKp:Sep;6earp;Geaoczp:RecKp:Sep;6egwp;Gep;Kep;LegDpxbbbbbbbbbbbbbbbbp:2egqarpxbbbjbbbjbbbjbbbjgkp9op9rp;Kegrpxbb;:9cbb;:9cbb;:9cbb;:9cararp;MeaDaDp;Meawaqawakp9op9rp;Kegrarp;Mep;Kep;Kep;Jep;Negwp;Mepxbbn0bbn0bbn0bbn0gqp;KepxFbbbFbbbFbbbFbbbp9oaopxbbbFbbbFbbbFbbbFp9op9qarawp;Meaqp;Kecwp:RepxbFbbbFbbbFbbbFbbp9op9qaDawp;Meaqp;Keczp:RepxbbFbbbFbbbFbbbFbp9op9qpklbkalaiad;8qbbskdnaec98GgxTmbcbhvabhdinadczfglalpbbbgopxbbbbbbFFbbbbbbFFgkp9oadpbbbgDaopmlvorxmPsCXQL358E8FpxFubbFubbFubbFubbp9op;6eaDaopmbediwDqkzHOAKY8AEgoczp:Sep;6egrp;Geaoczp:Reczp:Sep;6egwp;Gep;Kep;Legopxb;:FSb;:FSb;:FSb;:FSawaopxbbbbbbbbbbbbbbbbp:2egqawpxbbbjbbbjbbbjbbbjgmp9op9rp;Kegwawp;Meaoaop;Mearaqaramp9op9rp;Kegoaop;Mep;Kep;Kep;Jep;Negrp;Mepxbbn0bbn0bbn0bbn0gqp;Keczp:Reawarp;Meaqp;KepxFFbbFFbbFFbbFFbbp9op9qgwaoarp;Meaqp;KepxFFbbFFbbFFbbFFbbp9ogopmwDKYqk8AExm35Ps8E8Fp9qpkbbadaDakp9oawaopmbezHdiOAlvCXorQLp9qpkbbadcafhdavclfgvax6mbkkaxae9pmbaiaeciGgvcitgdfcbcaad9R;8kbaiabaxcitfglad;8qbbdnavTmbaiaipblzgopxbbbbbbFFbbbbbbFFgkp9oaipblbgDaopmlvorxmPsCXQL358E8FpxFubbFubbFubbFubbp9op;6eaDaopmbediwDqkzHOAKY8AEgoczp:Sep;6egrp;Geaoczp:Reczp:Sep;6egwp;Gep;Kep;Legopxb;:FSb;:FSb;:FSb;:FSawaopxbbbbbbbbbbbbbbbbp:2egqawpxbbbjbbbjbbbjbbbjgmp9op9rp;Kegwawp;Meaoaop;Mearaqaramp9op9rp;Kegoaop;Mep;Kep;Kep;Jep;Negrp;Mepxbbn0bbn0bbn0bbn0gqp;Keczp:Reawarp;Meaqp;KepxFFbbFFbbFFbbFFbbp9op9qgwaoarp;Meaqp;KepxFFbbFFbbFFbbFFbbp9ogopmwDKYqk8AExm35Ps8E8Fp9qpklzaiaDakp9oawaopmbezHdiOAlvCXorQLp9qpklbkalaiad;8qbbkk;4wllue97euv978Jjjjjbc8W9Rhidnaec98GglTmbcbhvabhoinaiaopbbbgraoczfgwpbbbgDpmlvorxmPsCXQL358E8Fgqczp:Segkclp:RepklbaopxbbjZbbjZbbjZbbjZpx;Zl81Z;Zl81Z;Zl81Z;Zl81Zakpxibbbibbbibbbibbbp9qp;6ep;NegkaraDpmbediwDqkzHOAKY8AEgrczp:Reczp:Sep;6ep;MegDaDp;Meakarczp:Sep;6ep;Megxaxp;Meakaqczp:Reczp:Sep;6ep;Megqaqp;Mep;Kep;Kep;Lepxbbbbbbbbbbbbbbbbp:4ep;Jepxb;:FSb;:FSb;:FSb;:FSgkp;Mepxbbn0bbn0bbn0bbn0grp;KepxFFbbFFbbFFbbFFbbgmp9oaxakp;Mearp;Keczp:Rep9qgxaqakp;Mearp;Keczp:ReaDakp;Mearp;Keamp9op9qgkpmbezHdiOAlvCXorQLgrp5baipblbpEb:T:j83ibaocwfarp5eaipblbpEe:T:j83ibawaxakpmwDKYqk8AExm35Ps8E8Fgkp5baipblbpEd:T:j83ibaocKfakp5eaipblbpEi:T:j83ibaocafhoavclfgval6mbkkdnalae9pmbaiaeciGgvcitgofcbcaao9R;8kbaiabalcitfgwao;8qbbdnavTmbaiaipblbgraipblzgDpmlvorxmPsCXQL358E8Fgqczp:Segkclp:RepklaaipxbbjZbbjZbbjZbbjZpx;Zl81Z;Zl81Z;Zl81Z;Zl81Zakpxibbbibbbibbbibbbp9qp;6ep;NegkaraDpmbediwDqkzHOAKY8AEgrczp:Reczp:Sep;6ep;MegDaDp;Meakarczp:Sep;6ep;Megxaxp;Meakaqczp:Reczp:Sep;6ep;Megqaqp;Mep;Kep;Kep;Lepxbbbbbbbbbbbbbbbbp:4ep;Jepxb;:FSb;:FSb;:FSb;:FSgkp;Mepxbbn0bbn0bbn0bbn0grp;KepxFFbbFFbbFFbbFFbbgmp9oaxakp;Mearp;Keczp:Rep9qgxaqakp;Mearp;Keczp:ReaDakp;Mearp;Keamp9op9qgkpmbezHdiOAlvCXorQLgrp5baipblapEb:T:j83ibaiarp5eaipblapEe:T:j83iwaiaxakpmwDKYqk8AExm35Ps8E8Fgkp5baipblapEd:T:j83izaiakp5eaipblapEi:T:j83iKkawaiao;8qbbkk:Pddiue978Jjjjjbc;ab9Rhidnadcd4ae2glc98GgvTmbcbhdabheinaeaepbbbgocwp:Recwp:Sep;6eaocep:SepxbbjZbbjZbbjZbbjZp:UepxbbjFbbjFbbjFbbjFp9op;Mepkbbaeczfheadclfgdav6mbkkdnaval9pmbaialciGgdcdtgeVcbc;abae9R;8kbaiabavcdtfgvae;8qbbdnadTmbaiaipblbgocwp:Recwp:Sep;6eaocep:SepxbbjZbbjZbbjZbbjZp:UepxbbjFbbjFbbjFbbjFp9op;Mepklbkavaiae;8qbbkk9teiucbcbydj1jjbgeabcifc98GfgbBdj1jjbdndnabZbcztgd9nmbcuhiabad9RcFFifcz4nbcuSmekaehikaikkkebcjwklz9Tbb",
      b = new Uint8Array([
        0, 97, 115, 109, 1, 0, 0, 0, 1, 4, 1, 96, 0, 0, 3, 3, 2, 0, 0, 5, 3, 1, 0, 1, 12, 1, 0, 10,
        22, 2, 12, 0, 65, 0, 65, 0, 65, 0, 252, 10, 0, 0, 11, 7, 0, 65, 0, 253, 15, 26, 11,
      ]),
      E = new Uint8Array([
        32, 0, 65, 2, 1, 106, 34, 33, 3, 128, 11, 4, 13, 64, 6, 253, 10, 7, 15, 116, 127, 5, 8, 12,
        40, 16, 19, 54, 20, 9, 27, 255, 113, 17, 42, 67, 24, 23, 146, 148, 18, 14, 22, 45, 70, 69,
        56, 114, 101, 21, 25, 63, 75, 136, 108, 28, 118, 29, 73, 115,
      ]);
    if (typeof WebAssembly != "object")
      return {
        supported: !1,
      };
    var T = WebAssembly.validate(b) ? y : ae,
      L,
      F = WebAssembly.instantiate(j(T), {}).then(function (gt) {
        ((L = gt.instance), L.exports.__wasm_call_ctors());
      });
    function j(gt) {
      for (var xt = new Uint8Array(gt.length), Xe = 0; Xe < gt.length; ++Xe) {
        var ut = gt.charCodeAt(Xe);
        xt[Xe] = ut > 96 ? ut - 97 : ut > 64 ? ut - 39 : ut + 4;
      }
      for (var dn = 0, Xe = 0; Xe < gt.length; ++Xe)
        xt[dn++] = xt[Xe] < 60 ? E[xt[Xe]] : (xt[Xe] - 60) * 64 + xt[++Xe];
      return xt.buffer.slice(0, dn);
    }
    function W(gt, xt, Xe, ut, dn, qt) {
      var ln = L.exports.sbrk,
        Tn = (Xe + 3) & -4,
        fn = ln(Tn * ut),
        Hn = ln(dn.length),
        En = new Uint8Array(L.exports.memory.buffer);
      En.set(dn, Hn);
      var Ei = gt(fn, Xe, ut, Hn, dn.length);
      if (
        (Ei == 0 && qt && qt(fn, Tn, ut),
        xt.set(En.subarray(fn, fn + Xe * ut)),
        ln(fn - ln(0)),
        Ei != 0)
      )
        throw new Error("Malformed buffer data: " + Ei);
    }
    var re = {
        NONE: "",
        OCTAHEDRAL: "meshopt_decodeFilterOct",
        QUATERNION: "meshopt_decodeFilterQuat",
        EXPONENTIAL: "meshopt_decodeFilterExp",
      },
      fe = {
        ATTRIBUTES: "meshopt_decodeVertexBuffer",
        TRIANGLES: "meshopt_decodeIndexBuffer",
        INDICES: "meshopt_decodeIndexSequence",
      },
      te = [],
      Te = 0;
    function Ge(gt) {
      var xt = {
        object: new Worker(gt),
        pending: 0,
        requests: {},
      };
      return (
        (xt.object.onmessage = function (Xe) {
          var ut = Xe.data;
          ((xt.pending -= ut.count),
            xt.requests[ut.id][ut.action](ut.value),
            delete xt.requests[ut.id]);
        }),
        xt
      );
    }
    function St(gt) {
      for (
        var xt =
            "var instance; var ready = WebAssembly.instantiate(new Uint8Array([" +
            new Uint8Array(j(T)) +
            "]), {}).then(function(result) { instance = result.instance; instance.exports.__wasm_call_ctors(); });self.onmessage = workerProcess;" +
            W.toString() +
            Vt.toString(),
          Xe = new Blob([xt], {
            type: "text/javascript",
          }),
          ut = URL.createObjectURL(Xe),
          dn = 0;
        dn < gt;
        ++dn
      )
        te[dn] = Ge(ut);
      URL.revokeObjectURL(ut);
    }
    function kt(gt, xt, Xe, ut, dn) {
      for (var qt = te[0], ln = 1; ln < te.length; ++ln)
        te[ln].pending < qt.pending && (qt = te[ln]);
      return new Promise(function (Tn, fn) {
        var Hn = new Uint8Array(Xe),
          En = Te++;
        ((qt.pending += gt),
          (qt.requests[En] = {
            resolve: Tn,
            reject: fn,
          }),
          qt.object.postMessage(
            {
              id: En,
              count: gt,
              size: xt,
              source: Hn,
              mode: ut,
              filter: dn,
            },
            [Hn.buffer],
          ));
      });
    }
    function Vt(gt) {
      F.then(function () {
        var xt = gt.data;
        try {
          var Xe = new Uint8Array(xt.count * xt.size);
          (W(L.exports[xt.mode], Xe, xt.count, xt.size, xt.source, L.exports[xt.filter]),
            self.postMessage(
              {
                id: xt.id,
                count: xt.count,
                action: "resolve",
                value: Xe,
              },
              [Xe.buffer],
            ));
        } catch (ut) {
          self.postMessage({
            id: xt.id,
            count: xt.count,
            action: "reject",
            value: ut,
          });
        }
      });
    }
    return {
      ready: F,
      supported: !0,
      useWorkers: function (gt) {
        St(gt);
      },
      decodeVertexBuffer: function (gt, xt, Xe, ut, dn) {
        W(L.exports.meshopt_decodeVertexBuffer, gt, xt, Xe, ut, L.exports[re[dn]]);
      },
      decodeIndexBuffer: function (gt, xt, Xe, ut) {
        W(L.exports.meshopt_decodeIndexBuffer, gt, xt, Xe, ut);
      },
      decodeIndexSequence: function (gt, xt, Xe, ut) {
        W(L.exports.meshopt_decodeIndexSequence, gt, xt, Xe, ut);
      },
      decodeGltfBuffer: function (gt, xt, Xe, ut, dn, qt) {
        W(L.exports[fe[dn]], gt, xt, Xe, ut, L.exports[re[qt]]);
      },
      decodeGltfBufferAsync: function (gt, xt, Xe, ut, dn) {
        return te.length > 0
          ? kt(gt, xt, Xe, fe[ut], re[dn])
          : F.then(function () {
              var qt = new Uint8Array(gt * xt);
              return (W(L.exports[fe[ut]], qt, gt, xt, Xe, L.exports[re[dn]]), qt);
            });
      },
    };
  })();
  class ye extends s.g {
    constructor() {
      super(...arguments);
      B(this, "extensions", ["gltf", "glb", "bin"]);
    }
    load({ url: b, file: E, onLoad: T, onProgress: L, onError: F }) {
      const j = (fe) => {
        const te = fe.scene;
        (Object.assign(te, {
          animations: fe.animations,
        }),
          Object.assign(te.meshData, (0, jo.tQ)(te)),
          T(te));
      };
      let W = new Fa(this.viewer.loadingManager),
        re = new da(this.viewer.loadingManager);
      (re.setDecoderPath(this.viewer.dracoPath),
        W.setDRACOLoader(re),
        W.setMeshoptDecoder(se),
        W.load(b, j, L, F, E));
    }
  }
  class ue extends m.yxD {
    constructor(y) {
      (super(y), (this.type = m.cLu));
    }
    parse(y) {
      const j = function (Xe, ut) {
          switch (Xe) {
            case 1:
              console.error("THREE.RGBELoader Read Error: " + (ut || ""));
              break;
            case 2:
              console.error("THREE.RGBELoader Write Error: " + (ut || ""));
              break;
            case 3:
              console.error("THREE.RGBELoader Bad File Format: " + (ut || ""));
              break;
            default:
            case 4:
              console.error("THREE.RGBELoader: Error: " + (ut || ""));
          }
          return -1;
        },
        te = `
`,
        Te = function (Xe, ut, dn) {
          ut = ut || 1024;
          let ln = Xe.pos,
            Tn = -1,
            fn = 0,
            Hn = "",
            En = String.fromCharCode.apply(null, new Uint16Array(Xe.subarray(ln, ln + 128)));
          for (; 0 > (Tn = En.indexOf(te)) && fn < ut && ln < Xe.byteLength;)
            ((Hn += En),
              (fn += En.length),
              (ln += 128),
              (En += String.fromCharCode.apply(null, new Uint16Array(Xe.subarray(ln, ln + 128)))));
          return -1 < Tn ? (dn !== !1 && (Xe.pos += fn + Tn + 1), Hn + En.slice(0, Tn)) : !1;
        },
        Ge = function (Xe) {
          const ut = /^#\?(\S+)/,
            dn = /^\s*GAMMA\s*=\s*(\d+(\.\d+)?)\s*$/,
            qt = /^\s*EXPOSURE\s*=\s*(\d+(\.\d+)?)\s*$/,
            ln = /^\s*FORMAT=(\S+)\s*$/,
            Tn = /^\s*\-Y\s+(\d+)\s+\+X\s+(\d+)\s*$/,
            fn = {
              valid: 0,
              string: "",
              comments: "",
              programtype: "RGBE",
              format: "",
              gamma: 1,
              exposure: 1,
              width: 0,
              height: 0,
            };
          let Hn, En;
          if (Xe.pos >= Xe.byteLength || !(Hn = Te(Xe))) return j(1, "no header found");
          if (!(En = Hn.match(ut))) return j(3, "bad initial token");
          for (
            fn.valid |= 1,
              fn.programtype = En[1],
              fn.string +=
                Hn +
                `
`;
            (Hn = Te(Xe)), Hn !== !1;
          ) {
            if (
              ((fn.string +=
                Hn +
                `
`),
              Hn.charAt(0) === "#")
            ) {
              fn.comments +=
                Hn +
                `
`;
              continue;
            }
            if (
              ((En = Hn.match(dn)) && (fn.gamma = parseFloat(En[1])),
              (En = Hn.match(qt)) && (fn.exposure = parseFloat(En[1])),
              (En = Hn.match(ln)) && ((fn.valid |= 2), (fn.format = En[1])),
              (En = Hn.match(Tn)) &&
                ((fn.valid |= 4),
                (fn.height = parseInt(En[1], 10)),
                (fn.width = parseInt(En[2], 10))),
              fn.valid & 2 && fn.valid & 4)
            )
              break;
          }
          return fn.valid & 2
            ? fn.valid & 4
              ? fn
              : j(3, "missing image size specifier")
            : j(3, "missing format specifier");
        },
        St = function (Xe, ut, dn) {
          const qt = ut;
          if (qt < 8 || qt > 32767 || Xe[0] !== 2 || Xe[1] !== 2 || Xe[2] & 128)
            return new Uint8Array(Xe);
          if (qt !== ((Xe[2] << 8) | Xe[3])) return j(3, "wrong scanline width");
          const ln = new Uint8Array(4 * ut * dn);
          if (!ln.length) return j(4, "unable to allocate buffer space");
          let Tn = 0,
            fn = 0;
          const Hn = 4 * qt,
            En = new Uint8Array(4),
            Ei = new Uint8Array(Hn);
          let ar = dn;
          for (; ar > 0 && fn < Xe.byteLength;) {
            if (fn + 4 > Xe.byteLength) return j(1);
            if (
              ((En[0] = Xe[fn++]),
              (En[1] = Xe[fn++]),
              (En[2] = Xe[fn++]),
              (En[3] = Xe[fn++]),
              En[0] != 2 || En[1] != 2 || ((En[2] << 8) | En[3]) != qt)
            )
              return j(3, "bad rgbe scanline format");
            let fr = 0,
              lr;
            for (; fr < Hn && fn < Xe.byteLength;) {
              lr = Xe[fn++];
              const Tr = lr > 128;
              if ((Tr && (lr -= 128), lr === 0 || fr + lr > Hn)) return j(3, "bad scanline data");
              if (Tr) {
                const Er = Xe[fn++];
                for (let Kr = 0; Kr < lr; Kr++) Ei[fr++] = Er;
              } else (Ei.set(Xe.subarray(fn, fn + lr), fr), (fr += lr), (fn += lr));
            }
            const is = qt;
            for (let Tr = 0; Tr < is; Tr++) {
              let Er = 0;
              ((ln[Tn] = Ei[Tr + Er]),
                (Er += qt),
                (ln[Tn + 1] = Ei[Tr + Er]),
                (Er += qt),
                (ln[Tn + 2] = Ei[Tr + Er]),
                (Er += qt),
                (ln[Tn + 3] = Ei[Tr + Er]),
                (Tn += 4));
            }
            ar--;
          }
          return ln;
        },
        kt = function (Xe, ut, dn, qt) {
          const ln = Xe[ut + 3],
            Tn = Math.pow(2, ln - 128) / 255;
          ((dn[qt + 0] = Xe[ut + 0] * Tn),
            (dn[qt + 1] = Xe[ut + 1] * Tn),
            (dn[qt + 2] = Xe[ut + 2] * Tn),
            (dn[qt + 3] = 1));
        },
        Vt = function (Xe, ut, dn, qt) {
          const ln = Xe[ut + 3],
            Tn = Math.pow(2, ln - 128) / 255;
          ((dn[qt + 0] = m.A5E.toHalfFloat(Math.min(Xe[ut + 0] * Tn, 65504))),
            (dn[qt + 1] = m.A5E.toHalfFloat(Math.min(Xe[ut + 1] * Tn, 65504))),
            (dn[qt + 2] = m.A5E.toHalfFloat(Math.min(Xe[ut + 2] * Tn, 65504))),
            (dn[qt + 3] = m.A5E.toHalfFloat(1)));
        },
        gt = new Uint8Array(y);
      gt.pos = 0;
      const xt = Ge(gt);
      if (xt !== -1) {
        const Xe = xt.width,
          ut = xt.height,
          dn = St(gt.subarray(gt.pos), Xe, ut);
        if (dn !== -1) {
          let qt, ln, Tn;
          switch (this.type) {
            case m.VzW:
              Tn = dn.length / 4;
              const fn = new Float32Array(Tn * 4);
              for (let En = 0; En < Tn; En++) kt(dn, En * 4, fn, En * 4);
              ((qt = fn), (ln = m.VzW));
              break;
            case m.cLu:
              Tn = dn.length / 4;
              const Hn = new Uint16Array(Tn * 4);
              for (let En = 0; En < Tn; En++) Vt(dn, En * 4, Hn, En * 4);
              ((qt = Hn), (ln = m.cLu));
              break;
            default:
              console.error("THREE.RGBELoader: unsupported type: ", this.type);
              break;
          }
          return {
            width: Xe,
            height: ut,
            data: qt,
            header: xt.string,
            gamma: xt.gamma,
            exposure: xt.exposure,
            type: ln,
          };
        }
      }
      return null;
    }
    setDataType(y) {
      return ((this.type = y), this);
    }
    load(y, b, E, T, L) {
      function F(j, W) {
        switch (j.type) {
          case m.VzW:
          case m.cLu:
            ((j.encoding = m.rnI),
              (j.minFilter = m.wem),
              (j.magFilter = m.wem),
              (j.generateMipmaps = !1),
              (j.flipY = !0));
            break;
        }
        b && b(j, W);
      }
      return super.load(y, F, E, T, L);
    }
  }
  class Ce extends s.g {
    constructor() {
      super(...arguments);
      B(this, "extensions", ["hdr"]);
    }
    load({ url: b, file: E, onLoad: T, onProgress: L, onError: F, texSettings: j }) {
      new ue(this.viewer.loadingManager).load(b, (W) => T(Object.assign(W, j)), L, F, E);
    }
  }
  class mt extends s.g {
    constructor() {
      super(...arguments);
      B(this, "extensions", ["json"]);
    }
    load({ url: b, file: E, onLoad: T, onProgress: L, onError: F }) {
      new _.hH6(this.viewer.loadingManager).load(b, (j) => T(JSON.parse(j)), L, F, E);
    }
  }
  class nn extends s.g {
    constructor() {
      super(...arguments);
      B(this, "extensions", ["png", "jpg", "webp", "avif"]);
    }
    load({ url: b, file: E, onLoad: T, onProgress: L, onError: F, texSettings: j }) {
      const W = this.viewer.renderer.outputEncoding;
      new _.dpR(this.viewer.loadingManager).load(
        b,
        (re) =>
          T(
            Object.assign(
              re,
              Object.assign(
                {
                  encoding: W,
                },
                j,
              ),
            ),
          ),
        L,
        F,
        E,
      );
    }
  }
  var cn = r(400);
  class ni extends s.g {
    constructor() {
      super(...arguments);
      B(this, "extensions", ["img"]);
    }
    load({ url: b, file: E, onLoad: T, onProgress: L, onError: F }) {
      (this.viewer.renderer.outputEncoding,
        new cn.S3k(this.viewer.loadingManager).load(b, T, L, F, E));
    }
  }
};
