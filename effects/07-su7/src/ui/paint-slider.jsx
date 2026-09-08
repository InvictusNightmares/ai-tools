import * as nt from "react";
import Oh from "react";
import { isPortrait } from "./../scene/orbit.js";
function Ls() {
  return (
    (Ls = Object.assign
      ? Object.assign.bind()
      : function (t) {
          for (var n = 1; n < arguments.length; n++) {
            var r = arguments[n];
            for (var s in r) Object.prototype.hasOwnProperty.call(r, s) && (t[s] = r[s]);
          }
          return t;
        }),
    Ls.apply(this, arguments)
  );
}
function Tx(t, n) {
  if (t == null) return {};
  var r = {},
    s = Object.keys(t),
    h,
    l;
  for (l = 0; l < s.length; l++) ((h = s[l]), !(n.indexOf(h) >= 0) && (r[h] = t[h]));
  return r;
}
var um = 100,
  ZU = (t) => {
    var { h: n, s: r, l: s, a: h } = qU(t);
    return "hsla(" + n + ", " + r + "%, " + s + "%, " + h + ")";
  },
  qU = (t) => {
    var { h: n, s: r, v: s, a: h } = t,
      l = ((200 - r) * s) / um;
    return {
      h: n,
      s: l > 0 && l < 200 ? ((r * s) / um / (l <= um ? l : 200 - l)) * um : 0,
      l: l / 2,
      a: h,
    };
  };
function GS(t) {
  var n = nt.useRef(t);
  return (
    nt.useEffect(() => {
      n.current = t;
    }),
    nt.useCallback((r, s) => n.current && n.current(r, s), [])
  );
}
var rf = (t) => "touches" in t,
  HS = (t) => {
    !rf(t) && t.preventDefault && t.preventDefault();
  },
  VS = function (n, r, s) {
    return (r === void 0 && (r = 0), s === void 0 && (s = 1), n > s ? s : n < r ? r : n);
  },
  WS = (t, n) => {
    var r = t.getBoundingClientRect(),
      s = rf(n) ? n.touches[0] : n;
    return {
      left: VS((s.pageX - (r.left + window.pageXOffset)) / r.width),
      top: VS((s.pageY - (r.top + window.pageYOffset)) / r.height),
      width: r.width,
      height: r.height,
      x: s.pageX - (r.left + window.pageXOffset),
      y: s.pageY - (r.top + window.pageYOffset),
    };
  },
  JU = ["prefixCls", "className", "onMove", "onDown"],
  kC = Oh.forwardRef((t, n) => {
    var { prefixCls: r = "w-color-interactive", className: s, onMove: h, onDown: l } = t,
      g = Tx(t, JU),
      _ = nt.useRef(null),
      A = nt.useRef(!1),
      [m, D] = nt.useState(!1),
      U = GS(h),
      R = GS(l),
      ne = (q) => (A.current && !rf(q) ? !1 : ((A.current = rf(q)), !0)),
      ce = nt.useCallback(
        (q) => {
          HS(q);
          var N = rf(q) ? q.touches.length > 0 : q.buttons > 0;
          N && _.current ? U && U(WS(_.current, q), q) : D(!1);
        },
        [U],
      ),
      xe = nt.useCallback(() => D(!1), []),
      Se = nt.useCallback((q) => {
        var N = q ? window.addEventListener : window.removeEventListener;
        (N(A.current ? "touchmove" : "mousemove", ce), N(A.current ? "touchend" : "mouseup", xe));
      }, []);
    nt.useEffect(
      () => (
        Se(m),
        () => {
          m && Se(!1);
        }
      ),
      [m, Se],
    );
    var $ = nt.useCallback(
      (q) => {
        (HS(q.nativeEvent),
          ne(q.nativeEvent) && (R && R(WS(_.current, q.nativeEvent), q.nativeEvent), D(!0)));
      },
      [R],
    );
    return (
      <div
        {...Ls({}, g, {
          className: [r, s || ""].filter(Boolean).join(" "),
          style: Ls({}, g.style, {
            touchAction: "none",
          }),
          ref: _,
          tabIndex: 0,
          onMouseDown: $,
          onTouchStart: $,
        })}
      />
    );
  });
kC.displayName = "Interactive";
const $U = kC;
var eN = ["className", "prefixCls", "left", "top", "style", "fillProps"],
  SliderPointer = (t) => {
    var { className: n, prefixCls: r, left: s, top: h, style: l, fillProps: g } = t,
      _ = Tx(t, eN),
      A = Ls({}, l, {
        position: "absolute",
        left: s,
        top: h,
      }),
      m = Ls(
        {
          width: 18,
          height: 18,
          boxShadow: "var(--alpha-pointer-box-shadow)",
          borderRadius: "50%",
          backgroundColor: "var(--alpha-pointer-background-color)",
        },
        g == null ? void 0 : g.style,
        {
          transform: s ? "translate(-9px, -1px)" : "translate(-1px, -9px)",
        },
      );
    return (
      <div
        {...Ls(
          {
            className: r + "-pointer " + (n || ""),
            style: A,
          },
          _,
          {
            children: (
              <div
                {...Ls(
                  {
                    className: r + "-fill",
                  },
                  g,
                  {
                    style: m,
                  },
                )}
              />
            ),
          },
        )}
      />
    );
  },
  nN = [
    "prefixCls",
    "className",
    "hsva",
    "background",
    "bgProps",
    "innerProps",
    "pointerProps",
    "radius",
    "width",
    "height",
    "direction",
    "style",
    "onChange",
    "pointer",
  ],
  iN =
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAMUlEQVQ4T2NkYGAQYcAP3uCTZhw1gGGYhAGBZIA/nYDCgBDAm9BGDWAAJyRCgLaBCAAgXwixzAS0pgAAAABJRU5ErkJggg==",
  UC = Oh.forwardRef((t, n) => {
    var {
        prefixCls: r = "w-color-alpha",
        className: s,
        hsva: h,
        background: l,
        bgProps: g = {},
        innerProps: _ = {},
        pointerProps: A = {},
        radius: m = 0,
        width: D,
        height: U = 16,
        direction: R = "horizontal",
        style: ne,
        onChange: ce,
        pointer: xe,
      } = t,
      Se = Tx(t, nN),
      $ = (Be) => {
        ce &&
          ce(
            Ls({}, h, {
              a: R === "horizontal" ? Be.left : Be.top,
            }),
            Be,
          );
      },
      q = ZU(
        Object.assign({}, h, {
          a: 1,
        }),
      ),
      N =
        "linear-gradient(to " +
        (R === "horizontal" ? "right" : "bottom") +
        ", rgba(244, 67, 54, 0) 0%, " +
        q +
        " 100%)",
      ie = {};
    R === "horizontal" ? (ie.left = h.a * 100 + "%") : (ie.top = h.a * 100 + "%");
    var _e = Ls(
        {
          "--alpha-background-color": "#fff",
          "--alpha-pointer-background-color": "rgb(248, 248, 248)",
          "--alpha-pointer-box-shadow": "rgb(0 0 0 / 37%) 0px 1px 4px 0px",
          borderRadius: m,
          background: "url(" + iN + ") left center",
          backgroundColor: "var(--alpha-background-color)",
        },
        {
          width: D,
          height: U,
        },
        ne,
        {
          position: "relative",
        },
      ),
      Pe =
        xe && typeof xe == "function" ? (
          xe(
            Ls(
              {
                prefixCls: r,
              },
              A,
              ie,
            ),
          )
        ) : (
          <SliderPointer
            {...Ls(
              {},
              A,
              {
                prefixCls: r,
              },
              ie,
            )}
          />
        );
    return (
      <div
        {...Ls({}, Se, {
          className: [r, r + "-" + R, s || ""].filter(Boolean).join(" "),
          style: _e,
          ref: n,
          children: [
            <div
              key="background"
              {...Ls({}, g, {
                style: Ls(
                  {
                    inset: 0,
                    position: "absolute",
                    background: l || N,
                    borderRadius: m,
                  },
                  g.style,
                ),
              })}
            />,
            <$U
              key="interaction"
              {...Ls({}, _, {
                style: Ls({}, _.style, {
                  inset: 0,
                  zIndex: 1,
                  position: "absolute",
                }),
                onMove: $,
                onDown: $,
                children: Pe,
              })}
            />,
          ],
        })}
      />
    );
  });
UC.displayName = "Alpha";
const AlphaControl = UC,
  Nh = Oh.forwardRef((t, n) => {
    const {
      prefixCls: r = "w-color-saturation",
      className: s,
      onChange: h,
      direction: l = "horizontal",
      backgroundGradient: g = "rgb(0, 0, 0),rgb(255, 255, 255)",
      hsva: _,
      ...A
    } = t;
    return (
      <AlphaControl
        ref={n}
        {...A}
        className={`${r} ${s || ""}`}
        hsva={{
          h: _.h,
          s: _.s,
          v: _.v,
          a: _.v / 100,
        }}
        direction={l}
        background={`linear-gradient(to ${l === "horizontal" ? "right" : "bottom"}, ${g})`}
        onChange={(m, D) => {
          isPortrait()
            ? h &&
              h({
                v: l === "horizontal" ? D.top * 100 : 100 - D.left * 100,
              })
            : h &&
              h({
                v: l === "horizontal" ? D.left * 100 : D.top * 100,
              });
        }}
      />
    );
  });
Nh.displayName = "ShadeSlider";
export {
  Ls,
  Tx,
  um,
  ZU,
  qU,
  GS,
  rf,
  HS,
  VS,
  WS,
  JU,
  kC,
  $U,
  eN,
  SliderPointer as tN,
  nN,
  iN,
  UC,
  AlphaControl as rN,
  Nh,
};
