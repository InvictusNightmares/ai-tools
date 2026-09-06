/* Scene behavior: controller-button-active. Registered in original execution order. */
var ControllerButtonActive = pc.createScript("controllerButtonActive");
ControllerButtonActive.attributes.add("buttons", {
  type: "entity",
  array: true,
  title: "按钮们",
});
ControllerButtonActive.attributes.add("colorButton", {
  type: "entity",
  title: "颜色按钮",
});
ControllerButtonActive.prototype.initialize = function () {
  this.app.on("HiddenButtons", this.hiddenButtons, this);
  this.app.on("ShowButtons", this.showAllButtons, this);
  this.app.on("controllerColorButton", this.setColorButtonShow, this);
};
ControllerButtonActive.prototype.update = function (t) {};
ControllerButtonActive.prototype.hiddenButtons = function (t) {
  for (i = 0; i < this.buttons.length; i++)
    i === t
      ? (this.buttons[i].enabled = true)
      : (this.buttons[i].enabled = false);
};
ControllerButtonActive.prototype.showAllButtons = function () {
  for (i = 0; i < this.buttons.length; i++) this.buttons[i].enabled = true;
};
ControllerButtonActive.prototype.setColorButtonShow = function (t) {
  this.colorButton.enabled = !t;
};
"undefined" != typeof document &&
  ((function (t, e) {
    function s(t, e) {
      for (var n in e)
        try {
          t.style[n] = e[n];
        } catch (t) {}
      return t;
    }
    function H(t) {
      return null == t
        ? String(t)
        : "object" == typeof t || "function" == typeof t
          ? Object.prototype.toString
              .call(t)
              .match(/\s([a-z]+)/i)[1]
              .toLowerCase() || "object"
          : typeof t;
    }
    function R(t, e) {
      if ("array" !== H(e)) return -1;
      if (e.indexOf) return e.indexOf(t);
      for (var n = 0, o = e.length; n < o; n++) if (e[n] === t) return n;
      return -1;
    }
    function I() {
      var t,
        e = arguments;
      for (t in e[1])
        if (e[1].hasOwnProperty(t))
          switch (H(e[1][t])) {
            case "object":
              e[0][t] = I({}, e[0][t], e[1][t]);
              break;
            case "array":
              e[0][t] = e[1][t].slice(0);
              break;
            default:
              e[0][t] = e[1][t];
          }
      return 2 < e.length
        ? I.apply(null, [e[0]].concat(Array.prototype.slice.call(e, 2)))
        : e[0];
    }
    function N(t) {
      return 1 === (t = Math.round(255 * t).toString(16)).length ? "0" + t : t;
    }
    function S(t, e, n, o) {
      t.addEventListener
        ? t[o ? "removeEventListener" : "addEventListener"](e, n, false)
        : t.attachEvent && t[o ? "detachEvent" : "attachEvent"]("on" + e, n);
    }
    function D(t, o) {
      function g(t, e, n, o) {
        return p[0 | t][Math.round(Math.min(((e - n) / (o - n)) * z, z))];
      }
      function r() {
        C.legend.fps !== L &&
          ((C.legend.fps = L), (C.legend[c] = L ? "FPS" : "ms"));
        w = L ? O.fps : O.duration;
        C.count[c] = 999 < w ? "999+" : w.toFixed(99 < w ? 0 : F.decimals);
      }
      function m() {
        for (
          l = n(),
            T < l - F.threshold &&
              ((O.fps -= O.fps / Math.max(1, (60 * F.smoothing) / F.interval)),
              (O.duration = 1000 / O.fps)),
            y = F.history;
          y--;
        ) {
          j[y] = 0 === y ? O.fps : j[y - 1];
          q[y] = 0 === y ? O.duration : q[y - 1];
        }
        if ((r(), F.heat)) {
          if (E.length)
            for (y = E.length; y--;)
              E[y].el.style[h[E[y].name].heatOn] = L
                ? g(h[E[y].name].heatmap, O.fps, 0, F.maxFps)
                : g(h[E[y].name].heatmap, O.duration, F.threshold, 0);
          if (C.graph && h.column.heatOn)
            for (y = M.length; y--;)
              M[y].style[h.column.heatOn] = L
                ? g(h.column.heatmap, j[y], 0, F.maxFps)
                : g(h.column.heatmap, q[y], F.threshold, 0);
        }
        if (C.graph)
          for (v = 0; v < F.history; v++)
            M[v].style.height =
              (L
                ? j[v]
                  ? Math.round((b / F.maxFps) * Math.min(j[v], F.maxFps))
                  : 0
                : q[v]
                  ? Math.round((b / F.threshold) * Math.min(q[v], F.threshold))
                  : 0) + "px";
      }
      function k() {
        20 > F.interval
          ? ((f = i(k)), m())
          : ((f = setTimeout(k, F.interval)), (x = i(m)));
      }
      function G(t) {
        (t = t || window.event).preventDefault
          ? (t.preventDefault(), t.stopPropagation())
          : ((t.returnValue = false), (t.cancelBubble = true));
        O.toggle();
      }
      function U() {
        F.toggleOn && S(C.container, F.toggleOn, G, 1);
        t.removeChild(C.container);
      }
      function V() {
        if (
          (C.container && U(),
          (h = D.theme[F.theme]),
          !(p = h.compiledHeatmaps || []).length && h.heatmaps.length)
        ) {
          for (v = 0; v < h.heatmaps.length; v++)
            for (p[v] = [], y = 0; y <= z; y++) {
              var e,
                n = p[v],
                o = y;
              e = (0.33 / z) * y;
              var a = h.heatmaps[v].saturation,
                i = h.heatmaps[v].lightness,
                l = void 0,
                c = void 0,
                u = void 0,
                d = (u = void 0),
                g = (l = c = void 0);
              g = void 0;
              0 === (u = 0.5 >= i ? i * (1 + a) : i + a - i * a)
                ? (e = "#000")
                : ((c = (u - (d = 2 * i - u)) / u),
                  (g = (e *= 6) - (l = Math.floor(e))),
                  (g *= u * c),
                  0 === l || 6 === l
                    ? ((l = u), (c = d + g), (u = d))
                    : 1 === l
                      ? ((l = u - g), (c = u), (u = d))
                      : 2 === l
                        ? ((l = d), (c = u), (u = d + g))
                        : 3 === l
                          ? ((l = d), (c = u - g))
                          : 4 === l
                            ? ((l = d + g), (c = d))
                            : ((l = u), (c = d), (u -= g)),
                  (e = "#" + N(l) + N(c) + N(u)));
              n[o] = e;
            }
          h.compiledHeatmaps = p;
        }
        for (var m in ((C.container = s(
          document.createElement("div"),
          h.container,
        )),
        (C.count = C.container.appendChild(
          s(document.createElement("div"), h.count),
        )),
        (C.legend = C.container.appendChild(
          s(document.createElement("div"), h.legend),
        )),
        (C.graph = F.graph
          ? C.container.appendChild(s(document.createElement("div"), h.graph))
          : 0),
        (E.length = 0),
        C))
          C[m] &&
            h[m].heatOn &&
            E.push({
              name: m,
              el: C[m],
            });
        if (((M.length = 0), C.graph))
          for (
            C.graph.style.width =
              F.history * h.column.width +
              (F.history - 1) * h.column.spacing +
              "px",
              y = 0;
            y < F.history;
            y++
          ) {
            M[y] = C.graph.appendChild(
              s(document.createElement("div"), h.column),
            );
            M[y].style.position = "absolute";
            M[y].style.bottom = 0;
            M[y].style.right = y * h.column.width + y * h.column.spacing + "px";
            M[y].style.width = h.column.width + "px";
            M[y].style.height = "0px";
          }
        s(C.container, F);
        r();
        t.appendChild(C.container);
        C.graph && (b = C.graph.clientHeight);
        F.toggleOn &&
          ("click" === F.toggleOn && (C.container.style.cursor = "pointer"),
          S(C.container, F.toggleOn, G));
      }
      "object" === H(t) && t.nodeType === e && ((o = t), (t = document.body));
      t || (t = document.body);
      var h,
        p,
        l,
        f,
        x,
        b,
        w,
        y,
        v,
        O = this,
        F = I({}, D.defaults, o || {}),
        C = {},
        M = [],
        z = 100,
        E = [],
        A = F.threshold,
        P = 0,
        T = n() - A,
        j = [],
        q = [],
        L = "fps" === F.show;
      O.options = F;
      O.fps = 0;
      O.duration = 0;
      O.isPaused = 0;
      O.tickStart = function () {
        P = n();
      };
      O.tick = function () {
        l = n();
        A += (l - T - A) / F.smoothing;
        O.fps = 1000 / A;
        O.duration = P < T ? A : l - P;
        T = l;
      };
      O.pause = function () {
        return (
          f && ((O.isPaused = 1), clearTimeout(f), a(f), a(x), (f = x = 0)),
          O
        );
      };
      O.resume = function () {
        return (f || ((O.isPaused = 0), k()), O);
      };
      O.set = function (t, e) {
        return (
          (F[t] = e),
          (L = "fps" === F.show),
          -1 !== R(t, u) && V(),
          -1 !== R(t, d) && s(C.container, F),
          O
        );
      };
      O.showDuration = function () {
        return (O.set("show", "ms"), O);
      };
      O.showFps = function () {
        return (O.set("show", "fps"), O);
      };
      O.toggle = function () {
        return (O.set("show", L ? "ms" : "fps"), O);
      };
      O.hide = function () {
        return (O.pause(), (C.container.style.display = "none"), O);
      };
      O.show = function () {
        return (O.resume(), (C.container.style.display = "block"), O);
      };
      O.destroy = function () {
        O.pause();
        U();
        O.tick = O.tickStart = function () {};
      };
      V();
      k();
    }
    var n,
      o = t.performance;
    n =
      o && (o.now || o.webkitNow)
        ? o[o.now ? "now" : "webkitNow"].bind(o)
        : function () {
            return +new Date();
          };
    for (
      var a = t.cancelAnimationFrame || t.cancelRequestAnimationFrame,
        i = t.requestAnimationFrame,
        h = 0,
        p = 0,
        l = (o = ["moz", "webkit", "o"]).length;
      p < l && !a;
      ++p
    )
      i =
        (a =
          t[o[p] + "CancelAnimationFrame"] ||
          t[o[p] + "CancelRequestAnimationFrame"]) &&
        t[o[p] + "RequestAnimationFrame"];
    a ||
      ((i = function (e) {
        var o = n(),
          a = Math.max(0, 16 - (o - h));
        return (
          (h = o + a),
          t.setTimeout(function () {
            e(o + a);
          }, a)
        );
      }),
      (a = function (t) {
        clearTimeout(t);
      }));
    var c =
      "string" === H(document.createElement("div").textContent)
        ? "textContent"
        : "innerText";
    D.extend = I;
    window.FPSMeter = D;
    D.defaults = {
      interval: 100,
      smoothing: 10,
      show: "fps",
      toggleOn: "click",
      decimals: 1,
      maxFps: 60,
      threshold: 100,
      position: "absolute",
      zIndex: 10,
      left: "5px",
      top: "5px",
      right: "auto",
      bottom: "auto",
      margin: "0 0 0 0",
      theme: "dark",
      heat: 0,
      graph: 0,
      history: 20,
    };
    var u = ["toggleOn", "theme", "heat", "graph", "history"],
      d = "position zIndex left top right bottom margin".split(" ");
  })(window),
  (function (t, e) {
    e.theme = {};
    var n = (e.theme.base = {
      heatmaps: [],
      container: {
        heatOn: null,
        heatmap: null,
        padding: "5px",
        minWidth: "95px",
        height: "30px",
        lineHeight: "30px",
        textAlign: "right",
        textShadow: "none",
      },
      count: {
        heatOn: null,
        heatmap: null,
        position: "absolute",
        top: 0,
        right: 0,
        padding: "5px 10px",
        height: "30px",
        fontSize: "24px",
        fontFamily: "Consolas, Andale Mono, monospace",
        zIndex: 2,
      },
      legend: {
        heatOn: null,
        heatmap: null,
        position: "absolute",
        top: 0,
        left: 0,
        padding: "5px 10px",
        height: "30px",
        fontSize: "12px",
        lineHeight: "32px",
        fontFamily: "sans-serif",
        textAlign: "left",
        zIndex: 2,
      },
      graph: {
        heatOn: null,
        heatmap: null,
        position: "relative",
        boxSizing: "padding-box",
        MozBoxSizing: "padding-box",
        height: "100%",
        zIndex: 1,
      },
      column: {
        width: 4,
        spacing: 1,
        heatOn: null,
        heatmap: null,
      },
    });
    e.theme.dark = e.extend({}, n, {
      heatmaps: [
        {
          saturation: 0.8,
          lightness: 0.8,
        },
      ],
      container: {
        background: "#222",
        color: "#fff",
        border: "1px solid #1a1a1a",
        textShadow: "1px 1px 0 #222",
      },
      count: {
        heatOn: "color",
      },
      column: {
        background: "#3f3f3f",
      },
    });
    e.theme.light = e.extend({}, n, {
      heatmaps: [
        {
          saturation: 0.5,
          lightness: 0.5,
        },
      ],
      container: {
        color: "#666",
        background: "#fff",
        textShadow:
          "1px 1px 0 rgba(255,255,255,.5), -1px -1px 0 rgba(255,255,255,.5)",
        boxShadow: "0 0 0 1px rgba(0,0,0,.1)",
      },
      count: {
        heatOn: "color",
      },
      column: {
        background: "#eaeaea",
      },
    });
    e.theme.colorful = e.extend({}, n, {
      heatmaps: [
        {
          saturation: 0.5,
          lightness: 0.6,
        },
      ],
      container: {
        heatOn: "backgroundColor",
        background: "#888",
        color: "#fff",
        textShadow: "1px 1px 0 rgba(0,0,0,.2)",
        boxShadow: "0 0 0 1px rgba(0,0,0,.1)",
      },
      column: {
        background: "#777",
        backgroundColor: "rgba(0,0,0,.2)",
      },
    });
    e.theme.transparent = e.extend({}, n, {
      heatmaps: [
        {
          saturation: 0.8,
          lightness: 0.5,
        },
      ],
      container: {
        padding: 0,
        color: "#fff",
        textShadow: "1px 1px 0 rgba(0,0,0,.5)",
      },
      count: {
        padding: "0 5px",
        height: "40px",
        lineHeight: "40px",
      },
      legend: {
        padding: "0 5px",
        height: "40px",
        lineHeight: "42px",
      },
      graph: {
        height: "40px",
      },
      column: {
        width: 5,
        background: "#999",
        heatOn: "backgroundColor",
        opacity: 0.5,
      },
    });
  })(window, FPSMeter));
