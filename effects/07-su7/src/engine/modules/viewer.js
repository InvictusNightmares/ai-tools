import { defineField as B } from "../fields.js";
// Recovered runtime module; preserve lazy initialization for cyclic dependencies.
export default (t, n, r) => {
  r.d(n, {
    A: () => Rt,
  });
  var s = r(25),
    h = r(353),
    l = r(461),
    g = r(779),
    _ = r(591);
  class A {
    constructor(pt) {
      B(this, "_targets", []);
      B(this, "_callback");
      this._callback = pt;
    }
    add(pt) {
      this._targets.push(pt);
    }
    remove(pt) {
      let Fe = this._targets.indexOf(pt);
      Fe !== -1 && this._targets.splice(Fe, 1);
    }
    invoke(pt) {
      let Fe = this._callback;
      for (let qe of this._targets) Fe(qe, pt);
    }
  }
  class m extends A {
    invoke(pt) {
      if (this._targets.length > 0) {
        let Fe = this._callback;
        for (let qe of this._targets) Fe(qe, pt);
        this._targets.length = 0;
      }
    }
  }
  const { Flags: D } = l.Entity;
  class U {
    constructor() {
      B(this, "startInvoker", new m((pt) => pt.start()));
      B(this, "updateInvoker", new A((pt, Fe) => pt.update(Fe)));
      B(this, "lastUpdateInvoker", new A((pt, Fe) => pt.lastUpdate(Fe)));
    }
    start() {
      this.startInvoker.invoke(0);
    }
    update(pt) {
      this.updateInvoker.invoke(pt);
    }
    lastUpdate(pt) {
      this.lastUpdateInvoker.invoke(pt);
    }
    enableComponent(pt, Fe) {
      Fe
        ? pt.__getFlag(D.OnEnableCalled) === !1 &&
          (pt.__setFlag(D.OnEnableCalled),
          pt.onEnable && pt.onEnable(),
          typeof pt.start == "function" &&
            !pt.__getFlag(D.IsStartCalled) &&
            (pt.__setFlag(D.IsStartCalled), this.startInvoker.add(pt)),
          typeof pt.update == "function" && this.updateInvoker.add(pt),
          typeof pt.lastUpdate == "function" && this.lastUpdateInvoker.add(pt))
        : pt.__getFlag(D.OnEnableCalled) &&
          (pt.__clearFlag(D.OnEnableCalled),
          pt.onDisable && pt.onDisable(),
          typeof pt.start == "function" &&
            !pt.__getFlag(D.IsStartCalled) &&
            this.startInvoker.remove(pt),
          typeof pt.update == "function" && this.updateInvoker.remove(pt),
          typeof pt.lastUpdate == "function" && this.lastUpdateInvoker.remove(pt));
    }
  }
  class R extends l.Entity {
    constructor() {
      super(...arguments);
      B(this, "_scheduler", new g.b());
      B(this, "_componentScheduler", new U());
    }
    get scheduler() {
      return this._scheduler;
    }
    get componentScheduler() {
      return this._componentScheduler;
    }
    update(Fe) {
      (this._scheduler.update(Fe),
        this._componentScheduler.start(),
        this._componentScheduler.update(Fe),
        this._componentScheduler.lastUpdate(Fe));
    }
    destroyNode(Fe) {
      (Fe.removeFromParent(), this.destroyComponents(Fe));
    }
    activeNode(Fe, qe) {
      ((Fe.visible = qe), this.activeComponents(Fe));
    }
    destroyComponents(Fe) {
      let qe = this._getComponents(Fe);
      for (let wt of qe) wt.destroy();
      Fe._components = [];
      for (let wt of Fe.children) this.destroyComponents(wt);
    }
    activeComponents(Fe) {
      let qe = Fe.visible;
      for (let wt of this._getComponents(Fe)) this._activeComponent(wt, qe);
      for (let wt of Fe.children) this.activeComponents(wt);
    }
    addComponent(Fe, qe) {
      let wt = Fe instanceof _.w ? Fe.node : Fe,
        An = typeof qe == "function",
        Qt = this._findComponent(wt, An ? qe : qe.constructor);
      if (Qt === void 0) {
        ((Qt = An ? new qe() : qe), (Qt.node = wt), (Qt.viewer = this));
        let Pi = Qt.__dependencies;
        if (Pi) for (let ui of Pi) this.getComponent(wt, ui) == null && this.addComponent(wt, ui);
        (Qt.__getFlag(l.Entity.Flags.OnLoadCalled) === !1 &&
          (Qt.__setFlag(l.Entity.Flags.OnLoadCalled),
          Qt.onInit && Qt.onInit(),
          Qt.onLoad && Qt.onLoad()),
          this._getComponents(wt).push(Qt),
          this._activeComponent(Qt, Qt.enabled));
      }
      return Qt;
    }
    removeComponent(Fe, qe) {
      let wt = this._getComponents(Fe),
        An = wt.indexOf(qe);
      return (An != -1 && wt.splice(An, 1), this);
    }
    getComponent(Fe, qe) {
      return this._findComponent(Fe, qe);
    }
    getComponentsInChidren(Fe, qe, wt = []) {
      let An = this._getComponents(Fe);
      for (let Qt = An.length; Qt--;) An[Qt] instanceof qe && wt.push(An[Qt]);
      for (let Qt of Fe.children) this.getComponentsInChidren(Qt, qe, wt);
      return wt;
    }
    _getComponents(Fe) {
      let qe = Fe._components;
      return (qe == null && (qe = Fe._components = []), qe);
    }
    _findComponent(Fe, qe) {
      let wt = this._getComponents(Fe);
      for (let An = wt.length; An--;) {
        let Qt = wt[An];
        if (Qt instanceof qe) return Qt;
      }
    }
    _activeComponent(Fe, qe) {
      this._componentScheduler.enableComponent(Fe, qe);
    }
  }
  var ne = r(694),
    ce = r(481),
    xe = r(992);
  class Se extends xe.S {
    update(pt) {
      ce.TweenManager.TweenUpdate();
    }
  }
  var $ = r(774),
    q = r(427),
    N = r(861);
  const ie = typeof window > "u";
  class _e {
    constructor(pt) {
      B(this, "userAgent");
      B(this, "isAndroidDevice");
      B(this, "iOSDevice");
      ((this.userAgent = pt || (!ie && window.navigator ? window.navigator.userAgent : "")),
        (this.isAndroidDevice =
          !/like android/i.test(this.userAgent) && /android/i.test(this.userAgent)),
        (this.iOSDevice = this.match(1, /(iphone|ipod|ipad)/i).toLowerCase()),
        !ie &&
          navigator.platform === "MacIntel" &&
          navigator.maxTouchPoints > 2 &&
          !window.MSStream &&
          (this.iOSDevice = "ipad"));
    }
    match(pt, Fe) {
      const qe = this.userAgent.match(Fe);
      return (qe && qe.length > 1 && qe[pt]) || "";
    }
    get isMobile() {
      return (
        !this.isTablet &&
        (/[^-]mobi/i.test(this.userAgent) ||
          this.iOSDevice === "iphone" ||
          this.iOSDevice === "ipod" ||
          this.isAndroidDevice ||
          /nexus\s*[0-6]\s*/i.test(this.userAgent))
      );
    }
    get isTablet() {
      return (
        (/tablet/i.test(this.userAgent) && !/tablet pc/i.test(this.userAgent)) ||
        this.iOSDevice === "ipad" ||
        (this.isAndroidDevice && !/[^-]mobi/i.test(this.userAgent)) ||
        (!/nexus\s*[0-6]\s*/i.test(this.userAgent) && /nexus\s*[0-9]+/i.test(this.userAgent))
      );
    }
    get isDesktop() {
      return !this.isMobile && !this.isTablet;
    }
    get isMacOS() {
      return (
        /macintosh/i.test(this.userAgent) && {
          version: this.match(1, /mac os x (\d+(\.?_?\d+)+)/i)
            .replace(/[_\s]/g, ".")
            .split(".")
            .map((pt) => pt)[1],
        }
      );
    }
    get isWindows() {
      return (
        /windows /i.test(this.userAgent) && {
          version: this.match(1, /Windows ((NT|XP)( \d\d?.\d)?)/i),
        }
      );
    }
    get isiOS() {
      return (
        !!this.iOSDevice && {
          version:
            this.match(1, /os (\d+([_\s]\d+)*) like mac os x/i).replace(/[_\s]/g, ".") ||
            this.match(1, /version\/(\d+(\.\d+)?)/i),
        }
      );
    }
    get isAndroid() {
      return (
        this.isAndroidDevice && {
          version: this.match(1, /android[ \/-](\d+(\.\d+)*)/i),
        }
      );
    }
    get browser() {
      const pt = this.match(1, /version\/(\d+(\.\d+)?)/i);
      return /opera/i.test(this.userAgent)
        ? {
            name: "Opera",
            version: pt || this.match(1, /(?:opera|opr|opios)[\s\/](\d+(\.\d+)?)/i),
          }
        : /opr\/|opios/i.test(this.userAgent)
          ? {
              name: "Opera",
              version: this.match(1, /(?:opr|opios)[\s\/](\d+(\.\d+)?)/i) || pt,
            }
          : /SamsungBrowser/i.test(this.userAgent)
            ? {
                name: "Samsung Internet for Android",
                version: pt || this.match(1, /(?:SamsungBrowser)[\s\/](\d+(\.\d+)?)/i),
              }
            : /yabrowser/i.test(this.userAgent)
              ? {
                  name: "Yandex Browser",
                  version: pt || this.match(1, /(?:yabrowser)[\s\/](\d+(\.\d+)?)/i),
                }
              : /ucbrowser/i.test(this.userAgent)
                ? {
                    name: "UC Browser",
                    version: this.match(1, /(?:ucbrowser)[\s\/](\d+(\.\d+)?)/i),
                  }
                : /msie|trident/i.test(this.userAgent)
                  ? {
                      name: "Internet Explorer",
                      version: this.match(1, /(?:msie |rv:)(\d+(\.\d+)?)/i),
                    }
                  : /(edge|edgios|edga|edg)/i.test(this.userAgent)
                    ? {
                        name: "Microsoft Edge",
                        version: this.match(2, /(edge|edgios|edga|edg)\/(\d+(\.\d+)?)/i),
                      }
                    : /firefox|iceweasel|fxios/i.test(this.userAgent)
                      ? {
                          name: "Firefox",
                          version: this.match(1, /(?:firefox|iceweasel|fxios)[ \/](\d+(\.\d+)?)/i),
                        }
                      : /chromium/i.test(this.userAgent)
                        ? {
                            name: "Chromium",
                            version: this.match(1, /(?:chromium)[\s\/](\d+(?:\.\d+)?)/i) || pt,
                          }
                        : /chrome|crios|crmo/i.test(this.userAgent)
                          ? {
                              name: "Chrome",
                              version: this.match(1, /(?:chrome|crios|crmo)\/(\d+(\.\d+)?)/i),
                            }
                          : /safari|applewebkit/i.test(this.userAgent)
                            ? {
                                name: "Safari",
                                version: pt,
                              }
                            : {
                                name: this.match(1, /^(.*)\/(.*) /),
                                version: this.match(2, /^(.*)\/(.*) /),
                              };
    }
  }
  const Pe = new _e(),
    Be = (navigator.userAgent || navigator.vendor).toLowerCase(),
    Re = typeof Pe.browser == "boolean" ? "" : Pe.browser.name,
    ct = document.createElement("audio");
  class et {
    constructor() {
      B(this, "isMobile", Pe.isMobile || Pe.isTablet);
      B(this, "isDesktop", Pe.isDesktop);
      B(this, "device", this.isMobile ? "mobile" : "desktop");
      B(this, "isAndroid", !!Pe.isAndroid);
      B(this, "isIOS", !!Pe.isiOS);
      B(this, "isMacOS", !!Pe.isMacOS);
      B(
        this,
        "isWindows",
        typeof Pe.isWindows == "boolean" ? Pe.isWindows : Pe.isWindows.version !== null,
      );
      B(this, "isLinux", Be.indexOf("linux") != -1);
      B(this, "ua", Be);
      B(this, "isEdge", Re === "Microsoft Edge");
      B(this, "isIE", Re === "Internet Explorer");
      B(this, "isFirefox", Re === "Firefox");
      B(this, "isChrome", Re === "Chrome");
      B(this, "isOpera", Re === "Opera");
      B(this, "isSafari", Re === "Safari");
      B(this, "isSupportMSAA", !Be.match("version/15.4 "));
      B(this, "isSupportOgg", !!ct.canPlayType("audio/ogg"));
      B(this, "isRetina", window.devicePixelRatio && window.devicePixelRatio >= 1.5);
      B(this, "devicePixelRatio", window.devicePixelRatio || 1);
      B(this, "cpuCoreCount", navigator.hardwareConcurrency || 1);
      B(this, "baseUrl", document.location.origin);
      B(this, "isIFrame", window.self !== window.top);
    }
  }
  var Ze = r(128),
    Nt = r(741);
  class Bt {
    constructor(pt, Fe) {
      B(this, "font");
      B(this, "texture");
      B(this, "material", null);
      ((this.font = pt),
        (this.texture = Fe),
        (this.material = new Nt.B()),
        (this.material.uniforms.texFont.value = Fe));
    }
    build(pt, Fe) {
      const qe = this.font,
        wt = qe.common.scaleW,
        An = qe.common.scaleH,
        Qt = pt.glyphs.filter((Gt) => Gt.data.width * Gt.data.height > 0),
        Pi = Fe.flipY !== !1,
        ui = new Float32Array(Qt.length * 8),
        mi = new Float32Array(Qt.length * 8),
        Si = new Uint16Array(Qt.length * 6);
      for (let Gt = 0, On = 0, kn = 0, bi = 0, $i = 0; $i < Qt.length; $i++, Gt += 4) {
        const zr = Qt[$i],
          Fi = zr.data;
        let vr = zr.position[0] + Fi.xoffset,
          Oi = zr.position[1] + Fi.yoffset,
          ts = Fi.width,
          Gr = Fi.height;
        ((ui[On++] = vr),
          (ui[On++] = Oi),
          (ui[On++] = vr + ts),
          (ui[On++] = Oi),
          (ui[On++] = vr + ts),
          (ui[On++] = Oi + Gr),
          (ui[On++] = vr),
          (ui[On++] = Oi + Gr));
        let ys = Fi.x + Fi.width,
          xs = Fi.y + Fi.height,
          hi = Fi.x / wt,
          Ti = Fi.y / An,
          gi = ys / wt,
          qi = xs / An;
        (Pi && ((Ti = 1 - Ti), (qi = 1 - qi)),
          (mi[kn++] = hi),
          (mi[kn++] = Ti),
          (mi[kn++] = gi),
          (mi[kn++] = Ti),
          (mi[kn++] = gi),
          (mi[kn++] = qi),
          (mi[kn++] = hi),
          (mi[kn++] = qi),
          (Si[bi++] = Gt + 0),
          (Si[bi++] = Gt + 1),
          (Si[bi++] = Gt + 2),
          (Si[bi++] = Gt + 0),
          (Si[bi++] = Gt + 2),
          (Si[bi++] = Gt + 3));
      }
      return {
        position: ui,
        uv: mi,
        indice: Si,
      };
    }
  }
  var en = r(745);
  class li extends en.g {
    constructor() {
      super(...arguments);
      B(this, "extensions", ["fnt"]);
    }
    load({ url: Fe, onLoad: qe, onProgress: wt, onError: An, texSettings: Qt }) {
      (async () => {
        try {
          let Pi = await this.viewer.loadAsset({
              url: Fe,
              selExt: "json",
            }),
            ui = await this.viewer.loadAsset({
              url: `${(0, q.I_)(Fe)}/${Pi.pages[0]}`,
              onProgress: wt,
            });
          qe(new Bt(Pi, Object.assign(ui, Qt)));
        } catch (Pi) {
          An(Pi);
        }
      })();
    }
  }
  var di = r(930);
  class xi {
    constructor(pt, Fe = "") {
      B(this, "excute");
      B(this, "name");
      ((this.excute = pt), (this.name = Fe));
    }
  }
  class zt extends di.v {
    constructor(Fe, qe, wt) {
      super();
      B(this, "onComplete");
      B(this, "onProgress");
      B(this, "onError");
      B(this, "_tasks", []);
      B(this, "_taskIndex", 0);
      B(this, "_percent", 0);
      ((this.onComplete = Fe), (this.onProgress = qe), (this.onError = wt));
    }
    get percent() {
      return this._percent;
    }
    add(Fe) {
      this._tasks.push(Fe);
    }
    update() {
      let Fe = this._tasks[this._taskIndex];
      if (Fe) {
        try {
          Fe.excute();
        } catch (qe) {
          (console.error(qe), this.onError && this.onError(Fe));
        }
        ((this._percent = ++this._taskIndex / this._tasks.length),
          this.onProgress && this.onProgress(Fe, this._taskIndex, this._tasks.length),
          this._taskIndex === this._tasks.length &&
            ((this._percent = 1), this.onComplete && this.onComplete()));
      }
    }
  }
  var Sn = r(371);
  let rn = new s.Pa4(),
    Ft = new s.Pa4(),
    jt = new s.FM8();
  function Xt(He, pt = []) {
    return typeof He == "function" ? new He(...pt) : He;
  }
  const Wn = class Wn extends R {
    constructor({
      root: Fe,
      canvas: qe = document.getElementById("canvas"),
      shadows: wt = !1,
      depth: An = !1,
      outputEncoding: Qt = s.knz,
      toneMapping: Pi = s.EoG,
      toneMappingExposure: ui = 1,
      camera: mi = {
        fov: 45,
        near: 1,
        far: 1e3,
        position: (0, N.nX)(0, 0, 4),
      },
      autoStart: Si = !0,
      autoResize: Gt = !0,
      floatPacking: On = !1,
      maxDPR: kn = 1.5,
      orientation: bi = Ze.i.AUTO,
      dracoPath: $i,
      targetFrameRate: zr,
      loader: Fi = {},
      tasker: vr = {},
      ...Oi
    } = {}) {
      super();
      B(this, "_width", 0);
      B(this, "_height", 0);
      B(this, "_running", !1);
      B(this, "_renderer");
      B(this, "_root");
      B(this, "_canvas");
      B(this, "_context");
      B(this, "_loadingManager");
      B(this, "_taskManager");
      B(this, "_scene");
      B(this, "_camera");
      B(this, "_viewport", {
        width: 1,
        height: 1,
        factor: 1,
      });
      B(this, "_input", new ne.i(this));
      B(this, "_caches", new Map());
      B(this, "_loaders", new Map());
      B(this, "_brower", new et());
      B(this, "_autoResize", !0);
      B(this, "_floatPacking", !1);
      B(this, "_targetFrameRate", null);
      B(this, "_orientation", Ze.i.AUTO);
      B(this, "_dracoPath", "https://www.gstatic.com/draco/versioned/decoders/1.5.5/");
      B(this, "_RENDER_TARGET_FLOAT_TYPE", s.cLu);
      B(this, "_DATA_FLOAT_TYPE", s.VzW);
      B(this, "_rootRotated", !1);
      B(this, "_maxDPR", 1.5);
      B(this, "_time", 0);
      B(this, "_lastTime", 0);
      let ts = {
          alpha: !1,
          depth: !0,
          stencil: !0,
          antialias: !1,
          premultipliedAlpha: !0,
          preserveDrawingBuffer: !1,
          powerPreference: "default",
          failIfMajorPerformanceCaveat: !1,
        },
        Gr = this._getContext(qe, Object.assign(ts, Oi));
      if (Gr === null) {
        console.error("Unsupport WebGL in current platform");
        return;
      }
      ((this._root = Fe || qe),
        (this._canvas = qe),
        (this._context = Gr),
        (this._maxDPR = kn),
        (this._scene = new s.xsS()),
        (this._camera = (0, N.$p)(
          new s.cPb(mi.fov, mi.aspect || qe.width / qe.height, mi.near, mi.far),
          mi,
        )),
        (this._renderer = new s.CP7({
          canvas: qe,
          context: Gr,
        })),
        this._renderer.setPixelRatio(this.dpr),
        (this._renderer.outputEncoding = Qt),
        (this._renderer.toneMapping = Pi),
        (this._renderer.toneMappingExposure = ui),
        (this._renderer.shadowMap.enabled = !!wt),
        (this._renderer.shadowMap.type = typeof wt == "boolean" ? s.ntZ : wt),
        (this._renderer.info.autoReset = !1),
        (this._autoResize = Gt),
        (this._orientation = bi),
        (this._loadingManager = new s.lLk(Fi.onLoad, Fi.onProgress, Fi.onError)),
        (this._taskManager = new zt(vr.onComplete, vr.onProgress, vr.onError)),
        this._input.addEventListeners(),
        this._setColorSpace(),
        this._addDefaultPlugins(),
        this._addDefaultLoaders(),
        $i && (this._dracoPath = $i),
        zr && (this.targetFrameRate = zr),
        Si && this.start(),
        this.printInfo());
    }
    get width() {
      return this._width;
    }
    get height() {
      return this._height;
    }
    get rootRotated() {
      return this._rootRotated;
    }
    get orientation() {
      return this._orientation;
    }
    get dracoPath() {
      return this._dracoPath;
    }
    get targetFrameRate() {
      return this._targetFrameRate;
    }
    set targetFrameRate(Fe) {
      if (Fe <= 0) throw Error("targetFrameRate must be greater than 0, or undefined.");
      this._targetFrameRate = Fe;
    }
    get RENDER_TARGET_FLOAT_TYPE() {
      return this._RENDER_TARGET_FLOAT_TYPE;
    }
    get DATA_FLOAT_TYPE() {
      return this._DATA_FLOAT_TYPE;
    }
    get floatPacking() {
      return this._floatPacking;
    }
    get canvas() {
      return this._canvas;
    }
    get context() {
      return this._context;
    }
    get brower() {
      return this._brower;
    }
    get autoResize() {
      return this._autoResize;
    }
    get environment() {
      return this._scene.userData.environment;
    }
    get background() {
      return this._scene.userData.background;
    }
    get input() {
      return this._input;
    }
    get time() {
      return this._time;
    }
    get renderer() {
      return this._renderer;
    }
    get scene() {
      return this._scene;
    }
    get camera() {
      return this._camera;
    }
    get dpr() {
      return Math.min(this._maxDPR, window.devicePixelRatio);
    }
    get viewport() {
      return this._viewport;
    }
    get size() {
      return this._renderer.getSize(jt);
    }
    get colorSpace() {
      return s.epp.enabled ? s.epp.workingColorSpace : "srgb";
    }
    get dom() {
      return this._renderer.domElement;
    }
    get loadingManager() {
      return this._loadingManager;
    }
    get root() {
      return this._root;
    }
    printInfo() {
      const Fe = this._renderer.getContext();
      console.log(
        [
          "Welcome to xviewer.js",
          "Three Version: " + s.UZH,
          "WebGL Version: " + Fe.getParameter(Fe.VERSION),
          "ColorSpace: " + this.colorSpace,
        ].join(`
`),
      );
    }
    _getContext(Fe, qe) {
      const wt = this._brower;
      if (!((wt.isChrome || wt.isSafari || wt.isEdge || wt.isFirefox || wt.isOpera) && !wt.isIE))
        return (console.error("Unsupport platform"), null);
      if (!(Fe instanceof HTMLCanvasElement)) return (console.error("Canvas is null"), null);
      if (window.WebGL2RenderingContext)
        try {
          let Qt = Fe.getContext("webgl2", qe);
          return ((this._RENDER_TARGET_FLOAT_TYPE = s.cLu), (this._DATA_FLOAT_TYPE = s.VzW), Qt);
        } catch (Qt) {
          return (console.error(Qt), null);
        }
      else if (window.WebGLRenderingContext) {
        let Qt =
          Fe.getContext("webgl", qe) ||
          Fe.getContext("webgl2", qe) ||
          Fe.getContext("experimental-webgl", qe);
        return (Qt.getExtension("OES_texture_float") ||
          Qt.getExtension("OES_texture_half_float")) &&
          Qt.getParameter(Qt.MAX_VERTEX_TEXTURE_IMAGE_UNITS)
          ? ((this._RENDER_TARGET_FLOAT_TYPE =
              this._brower.isIOS || Qt.getExtension("OES_texture_half_float") ? s.cLu : s.VzW),
            (this._DATA_FLOAT_TYPE = s.VzW),
            Qt)
          : this._floatPacking
            ? ((this._RENDER_TARGET_FLOAT_TYPE = this._DATA_FLOAT_TYPE = s.ywz), Qt)
            : (console.log("Unspport float type in current platform"), null);
      }
      return null;
    }
    _setColorSpace() {
      s.epp.enabled = this.renderer.outputEncoding === s.knz;
    }
    _addDefaultPlugins() {
      this.addPlugin(Se);
    }
    _addDefaultLoaders() {
      (this.addLoader(h.f0),
        this.addLoader(h.GP),
        this.addLoader(h.q7),
        this.addLoader(h.Ae),
        this.addLoader(h.uo),
        this.addLoader(h.k7),
        this.addLoader(h.Zt),
        this.addLoader(h.YQ),
        this.addLoader(li),
        this.addLoader(h.KC));
    }
    _onPreDestroy() {
      (this._caches.clear(),
        this._renderer.dispose(),
        this._input.removeAllListeners(),
        this.destroyComponents(this._scene),
        this.stop());
    }
    async load({
      url: Fe,
      settings: qe,
      clear: wt = !1,
      castShadow: An = !1,
      receiveShadow: Qt = !1,
      parent: Pi = this._scene,
      onProgress: ui,
      ...mi
    }) {
      const Si = await this.loadAsset({
        url: Fe,
        onProgress: ui,
        ...mi,
      });
      return (
        (An || Qt) &&
          Si.meshData.meshes.forEach((Gt) => {
            ((Gt.castShadow = An), (Gt.receiveShadow = Qt));
          }),
        wt && Pi.clear(),
        this.addNode(Si, mi),
        Si
      );
    }
    loadAsset({ url: Fe, selExt: qe, onProgress: wt, ...An }) {
      return new Promise((Qt, Pi) => {
        const { url: ui, file: mi, ext: Si } = (0, q.BR)(Fe),
          Gt = (0, q.G)(An),
          On = (0, q.bk)(ui, Gt);
        let kn = this._caches.get(On);
        if (kn) Qt(kn);
        else {
          const bi = (zr) => {
            (this._caches.set(On, zr), Qt(zr));
          };
          let $i = qe || Si;
          this._loaders.has($i)
            ? this._loaders.get($i).load({
                url: ui,
                file: mi,
                texSettings: Gt,
                onProgress: wt,
                onLoad: bi,
                onError: Pi,
              })
            : Pi("missing loader for " + Si);
        }
      });
    }
    addLoader(Fe) {
      let qe = new Fe(this);
      for (let wt of qe.extensions) this._loaders.set(wt, qe);
      return this;
    }
    async setEnvironment(Fe = {}) {
      let qe = Fe.url ?? null;
      (this._scene.userData.environment !== qe &&
        ((this._scene.userData.environment = qe),
        (this._scene.environment = qe
          ? await this.loadAsset(
              Object.assign(
                {
                  mapping: s.dSO,
                },
                Fe,
              ),
            )
          : null)),
        (Fe && Fe.noBackground) || this.setBackground(Fe));
    }
    async setBackground(Fe) {
      let qe = Fe.color || Fe.url || null;
      this._scene.userData.background !== qe &&
        ((this._scene.userData.background = qe),
        (this._scene.background = qe
          ? Fe.color ||
            (await this.loadAsset(
              Object.assign(
                {
                  mapping: s.dSO,
                },
                Fe,
              ),
            ))
          : null));
    }
    portal(Fe) {
      const qe = this._scene,
        wt = this._camera;
      this._scene = new s.xsS();
      const An = Fe();
      return ((this._scene = qe), (this._camera = wt), An);
    }
    addNode(
      Fe,
      {
        scale: qe,
        position: wt,
        rotation: An,
        debug: Qt,
        shadowArgs: Pi,
        makeDefault: ui,
        args: mi,
        parent: Si = this._scene,
        components: Gt = [],
        ...On
      } = {},
    ) {
      let kn,
        bi = Xt(Fe, mi);
      if (bi.isObject3D) {
        ((kn = bi), Si.add(bi));
        for (let $i of Gt) (this.addComponent(kn, $i.ins), (0, N.$p)($i.ins, $i.props));
      } else if (bi.isComponent)
        ((kn = bi.node || new s.Tme()), Si.add(kn), this.addComponent(kn, bi));
      else throw Error("unsuport object");
      return (
        (0, N.$p)(bi, On, !0),
        (0, N.$p)(kn, {
          scale: qe,
          position: wt,
          rotation: An,
        }),
        bi.isCamera && ui && ((bi.manual = bi.aspect !== this.camera.aspect), (this._camera = bi)),
        Pi && kn.isDirectionalLight && (0, $.lK)(kn.shadow, Pi),
        Qt && (kn.userData.debug = Qt),
        bi
      );
    }
    addTask(Fe, qe) {
      this._taskManager.add(new xi(Fe, qe));
    }
    addPlugin(Fe, { args: qe, ...wt } = {}) {
      let An = Xt(Fe, qe);
      return (this.addComponent(this._scene, An), (0, N.$p)(An, wt), An);
    }
    getPlugin(Fe) {
      return this.getComponent(this._scene, Fe);
    }
    requirePlugin(Fe) {
      let qe = this.getPlugin(Fe);
      return (qe === void 0 && (qe = this.addPlugin(Fe)), qe);
    }
    component(Fe, { args: qe, ...wt } = {}) {
      return {
        ins: Xt(Fe, qe),
        props: wt,
      };
    }
    resize(Fe = window.innerWidth, qe = window.innerHeight) {
      if (
        ((this._rootRotated =
          this._orientation === Ze.i.LANDSCAPE
            ? Fe < qe
            : this._orientation === Ze.i.PORTRAIT
              ? Fe > qe
              : !1),
        this._rootRotated)
      ) {
        let wt = Fe;
        ((Fe = qe), (qe = wt));
      }
      if (this._width !== Fe || this._height !== qe) {
        ((this._width = Fe), (this._height = qe));
        let wt = this._root;
        this._rootRotated
          ? ((wt.style["-webkit-transform"] = "rotate(90deg)"),
            (wt.style.transform = "rotate(90deg)"),
            (wt.style["-webkit-transform-origin"] = "0px 0px 0px"),
            (wt.style.transformOrigin = "0px 0px 0px"),
            (wt.style.margin = `0 0 0 ${qe}px`),
            (wt.style.width = `${Fe}px`),
            (wt.style.height = `${qe}px`))
          : ((wt.style["-webkit-transform"] = "rotate(0deg)"),
            (wt.style.transform = "rotate(0deg)"),
            (wt.style.margin = "0px auto"),
            (wt.style.width = `${Fe}px`),
            (wt.style.height = `${qe}px`));
        let An = this._camera;
        if (An.isOrthographicCamera)
          this._viewport = {
            width: Fe / An.zoom,
            height: qe / An.zoom,
            factor: 1,
          };
        else if (An.isPerspectiveCamera) {
          An.manual || ((An.aspect = Fe / qe), An.updateProjectionMatrix());
          let Qt = An.getWorldPosition(Ft).distanceTo(rn),
            Pi = 2 * Math.tan(s.MathUtils.degToRad(An.fov * 0.5)) * Qt,
            ui = (Pi * Fe) / qe;
          this._viewport = {
            width: ui,
            height: Pi,
            factor: Fe / ui,
          };
        }
        (this.resizeCallback(Fe, qe), this.emit(ne.i.RESIZE, Fe, qe));
      }
    }
    render(Fe) {
      (this._renderer.info.reset(), this.renderCallback(Fe));
    }
    resizeCallback(Fe, qe) {
      this._renderer.setSize(Fe, qe);
    }
    renderCallback(Fe) {
      this._renderer.render(this._scene, this._camera);
    }
    loop(Fe) {
      (this._autoResize && this.resize(),
        (Fe = Math.min(Fe, 0.067)),
        this.update(Fe),
        this.emit(Wn.RENDER_BEFORE),
        this.render(Fe),
        this.emit(Wn.RENDER_AFTER));
    }
    _frame(Fe) {
      if (((this._time = Fe), this._taskManager.update(), (0, N.ri)(this._targetFrameRate))) {
        const qe = 1 / this._targetFrameRate,
          wt = Fe - this._lastTime;
        wt >= qe && (this.loop(wt), (this._lastTime = Fe - (wt % qe)));
      } else (this.loop(Fe - this._lastTime), (this._lastTime = Fe));
    }
    start() {
      if (this._running == !1) {
        this._running = !0;
        const Fe = (qe) => {
          this._running && (this._frame(qe * 0.001), requestAnimationFrame(Fe));
        };
        requestAnimationFrame(Fe);
      }
      return this;
    }
    stop() {
      return ((this._running = !1), (this._time = this._lastTime = 0), this);
    }
    compile(Fe) {
      if (Array.isArray(Fe)) {
        if (Fe.every((qe) => qe.isMaterial))
          (0, Sn.Wr)(this._renderer, this._scene, this._camera, Fe);
        else throw Error("unsuport material");
      } else
        typeof Fe == "object"
          ? Fe.isMaterial
            ? (0, Sn.Wr)(this._renderer, this._scene, this._camera, Fe)
            : Fe.isObject3D
              ? (Fe.meshData.materials &&
                  (0, Sn.Wr)(
                    this._renderer,
                    this._scene,
                    this._camera,
                    Object.values(Fe.meshData.materials),
                  ),
                Fe.meshData.textures &&
                  (0, Sn.$S)(this._renderer, Object.values(Fe.meshData.textures)),
                Fe.meshData.meshes || (0, Sn.EK)(this._renderer, this._scene, this._camera, Fe))
              : Fe.isTexture && (0, Sn.$S)(this._renderer, Fe)
          : (0, Sn.EK)(this._renderer, this._scene, this._camera, this._scene);
    }
    createRenderTarget(Fe, qe, wt = !1, An = !1, Qt = 0, Pi = !1) {
      return new s.dd2(Fe, qe, {
        wrapS: s.uWy,
        wrapT: s.uWy,
        magFilter: wt ? s.TyD : s.wem,
        minFilter: wt ? s.TyD : Pi ? s.FDw : s.wem,
        type: typeof An == "boolean" ? (An ? this.DATA_FLOAT_TYPE : s.ywz) : An,
        anisotropy: 0,
        encoding: s.rnI,
        depthBuffer: !1,
        stencilBuffer: !1,
        samples: this._brower.isSupportMSAA ? Qt : 0,
        generateMipmaps: Pi,
      });
    }
    createCubeRenderTarget(Fe, qe = !1, wt = !1, An = 0, Qt = !1) {
      return new s.oAp(Fe, {
        wrapS: s.uWy,
        wrapT: s.uWy,
        magFilter: qe ? s.TyD : s.wem,
        minFilter: qe ? s.TyD : Qt ? s.FDw : s.wem,
        type: typeof wt == "boolean" ? (wt ? this.DATA_FLOAT_TYPE : s.ywz) : wt,
        anisotropy: 0,
        encoding: s.rnI,
        depthBuffer: !1,
        stencilBuffer: !1,
        samples: this._brower.isSupportMSAA ? An : 0,
        generateMipmaps: Qt,
      });
    }
    createDataTexture(Fe, qe, wt, An = !1, Qt = !0) {
      return new s.IEO(
        Fe,
        qe,
        wt,
        s.wk1,
        An ? s.VzW : s.ywz,
        s.xfE,
        s.uWy,
        s.uWy,
        Qt ? s.TyD : s.wem,
        Qt ? s.TyD : s.wem,
        0,
      );
    }
  };
  (B(Wn, "RENDER_BEFORE", "renderbefore"),
    B(Wn, "RENDER_AFTER", "renderafter"),
    B(Wn, "ATTACH_HELPER", "attachhelper"));
  let Rt = Wn;
};
