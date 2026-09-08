import {
  PerspectiveCamera,
  Vector3,
  Mesh,
  SphereGeometry,
  Material,
  Vector2,
  Euler,
  Quaternion,
  Component,
  InputEvents,
  Tweening,
} from "./../engine/index.js";
import { defineField as B } from "./../engine/fields.js";
import { events, ShowState } from "./../state/events.js";
function isMobile() {
  const t = navigator.userAgent;
  return /iPad/.test(t) ? !1 : /Mobile|Android|iPhone|iPod|BlackBerry|Windows Phone|iPad/gi.test(t);
}
function isPortrait() {
  const t = document.documentElement.clientWidth,
    n = document.documentElement.clientHeight;
  return !(t > n);
}
const cM = new PerspectiveCamera();
cM.position.set(5, 0, 0);
cM.lookAt(new Vector3(0, 0, 0));
new Mesh(new SphereGeometry(1), [new Material()]);
function rl(t, n, r) {
  return t + (n - t) * r;
}
function TO(t, n, r) {
  return ((n.x = rl(0, t.x, r)), (n.y = rl(0, t.y, r)), (n.z = rl(0, t.z, r)), n);
}
function EO(t, n) {
  ((t.x -= n.x), (t.y -= n.y), (t.z -= n.z));
}
function MO(t, n) {
  ((t.x += n.x), (t.y += n.y), (t.z += n.z));
}
function _A(t, n, r) {
  return ((t = Math.max(n, t)), (t = Math.min(r, t)), t);
}
function yA() {
  return "maxTouchPoints" in navigator && navigator.maxTouchPoints > 0;
}
const $u = new Vector2(),
  Ev = new Euler(),
  Bd = new Quaternion(),
  xA = new Quaternion(),
  CO = new Euler();
class OrbitController extends Component {
  constructor({ springCamera: r }) {
    super();
    B(this, "enableClamp", !0);
    B(this, "targetFov", 45);
    B(this, "springlengthOffset", 0);
    B(this, "lerpStrength", 1);
    B(this, "moveSpeed", [1, 1]);
    B(this, "_currentLengthOffset", 0);
    B(this, "_springRotationZClampRange", [0.02, 0.3]);
    B(this, "_springRotationYClampRange", [-100, 100]);
    B(this, "_deltaRotation", new Euler());
    B(this, "_targetRotation", new Euler());
    B(this, "_targetSpringLength", 0);
    B(this, "_targetLookAt", new Vector3());
    B(this, "_button", -1);
    B(this, "_preLoc0", new Vector2());
    B(this, "_preLoc1", new Vector2());
    B(this, "_touchID");
    B(this, "_springCamera");
    B(this, "_enableControlCamera", !1);
    B(this, "_lerpQuatStrength", 5);
    B(this, "_lerpLengthStrength", 3);
    B(this, "_mouseWheelSum", 0);
    this.onLoad = () => {
      ((this._springCamera = r), this.reset());
    };
  }
  get lerpLengthStrength() {
    return this._lerpLengthStrength;
  }
  set lerpLengthStrength(r) {
    this._lerpLengthStrength = r;
  }
  get springLength() {
    return this._targetSpringLength;
  }
  set springLength(r) {
    this._targetSpringLength = r;
  }
  get enableControlCamera() {
    return this._enableControlCamera;
  }
  set enableControlCamera(r) {
    this._enableControlCamera !== r &&
      ((this._enableControlCamera = r),
      r
        ? (yA()
            ? (this.viewer.on(InputEvents.TOUCH_START, this._onTouchStart, this),
              this.viewer.on(InputEvents.TOUCH_MOVE, this._onTouchMove, this))
            : (this.viewer.on(InputEvents.POINTER_DOWN, this._onMouseDown, this),
              this.viewer.on(InputEvents.POINTER_UP, this._onMouseUp, this),
              this.viewer.on(InputEvents.POINTER_MOVE, this._onMouseMove, this)),
          this.viewer.on(InputEvents.MOUSE_WHEEL, this._onMouseWheel, this),
          this.reset())
        : (yA()
            ? (this.viewer.off(InputEvents.TOUCH_START, this._onTouchStart, this),
              this.viewer.off(InputEvents.TOUCH_MOVE, this._onTouchMove, this))
            : (this.viewer.off(InputEvents.POINTER_DOWN, this._onMouseDown, this),
              this.viewer.off(InputEvents.POINTER_UP, this._onMouseUp, this),
              this.viewer.off(InputEvents.POINTER_MOVE, this._onMouseMove, this)),
          this.viewer.off(InputEvents.MOUSE_WHEEL, this._onMouseWheel, this)));
  }
  reset() {
    ((this._button = -1),
      (this._touchID = -1),
      (this.springLength = this._springCamera.springLength),
      this._targetLookAt.copy(this._springCamera.lookAt),
      this._targetRotation.copy(this._springCamera.rotation),
      this._deltaRotation.set(0, 0, 0),
      (this.targetFov = this.viewer.camera.fov));
  }
  _onMouseDown(r) {
    ((this._button = r.button), this._preLoc0.set(r.pageX, r.pageY));
  }
  _onMouseUp(r) {
    this._button = -1;
  }
  _onMouseMove(r) {
    switch (($u.set(r.pageX, r.pageY), this._button)) {
      case 0:
        (this._preLoc0.sub($u).multiplyScalar(this._springCamera.springLength * 0.001),
          this.updateDeltaRotation());
        break;
    }
    this._preLoc0.copy($u);
  }
  updateDeltaRotation() {
    ((this._deltaRotation.y += this._preLoc0.x * this.moveSpeed[0]),
      (this._deltaRotation.z -= this._preLoc0.y * this.moveSpeed[1]));
  }
  _onMouseWheel(r) {
    ((this._mouseWheelSum += r.deltaY),
      this._mouseWheelSum > 200
        ? ((this._mouseWheelSum = 0), changeSection(!0))
        : this._mouseWheelSum < -200 && ((this._mouseWheelSum = 0), changeSection(!1)));
  }
  _onTouchStart(r) {
    const s = r.touches;
    (s.length == 1 &&
      (this._preLoc0.set(s[0].pageX, s[0].pageY), (this._touchID = r.touches[0].identifier)),
      s.length > 1 &&
        (this._preLoc1.set(s[1].pageX, s[1].pageY),
        console.log(
          "preLoc1=" + Math.round(this._preLoc1.x) + "  " + Math.round(this._preLoc1.y),
        )));
  }
  _onTouchMove(r) {
    const s = r.touches;
    s.length === 1 &&
      this._touchID === s[0].identifier &&
      ($u.set(s[0].pageX, s[0].pageY),
      this._preLoc0.sub($u).multiplyScalar(this._springCamera.springLength * 0.0016),
      this.updateDeltaRotation(),
      this._preLoc0.copy($u));
  }
  update(r) {
    (Math.abs(this.viewer.camera.fov - this.targetFov) > 0.01 &&
      ((this.viewer.camera.fov = rl(this.viewer.camera.fov, this.targetFov, this.lerpStrength * r)),
      this.viewer.camera.updateProjectionMatrix()),
      (this._currentLengthOffset = rl(
        this._currentLengthOffset,
        this.springlengthOffset,
        this.lerpStrength * r,
      )));
    const s = this._targetSpringLength + this._currentLengthOffset;
    (this._springCamera.lookAt.lerp(this._targetLookAt, r),
      (this._springCamera.springLength = rl(
        this._springCamera.springLength,
        s,
        0.016 * this._lerpLengthStrength,
      )),
      TO(this._deltaRotation, Ev, r * 10),
      EO(this._deltaRotation, Ev),
      MO(this._targetRotation, Ev),
      Bd.setFromEuler(this._targetRotation),
      this._targetRotation.setFromQuaternion(Bd, "YZX"),
      this.enableClamp &&
        ((this._targetRotation.z = _A(
          this._targetRotation.z,
          this._springRotationZClampRange[0],
          this._springRotationZClampRange[1],
        )),
        (this._targetRotation.y = _A(
          this._targetRotation.y,
          this._springRotationYClampRange[0],
          this._springRotationYClampRange[1],
        ))),
      Bd.setFromEuler(this._springCamera.rotation),
      xA.setFromEuler(this._targetRotation),
      Bd.slerp(xA, r * this._lerpQuatStrength),
      this._springCamera.rotation.copy(CO.setFromQuaternion(Bd, "YZX")));
  }
  gotoPOI(r, s, h, l = 1.5, g = Tweening.Easing.Cubic.InOut, _ = 0) {
    return new Promise((A) => {
      var m;
      (Tweening.TweenManager.KillTweensOf(this),
        Tweening.TweenManager.Timeline(this)
          .delay(l)
          .call(() => {
            this.reset();
          })
          .start(),
        (m = this._springCamera) == null ||
          m.gotoPOI(r, s, h, l, g, _).then(() => {
            A(!0);
          }));
    });
  }
  setNewTarget(r, s, h) {
    (this.reset(),
      (this._lerpQuatStrength = 0),
      Tweening.TweenManager.KillTweensOf(this),
      Tweening.TweenManager.Timeline(this)
        .to(
          {
            _lerpQuatStrength: 5,
          },
          1,
        )
        .start(),
      (this.springLength = s),
      this._targetLookAt.copy(r),
      this._targetRotation.copy(h));
  }
  setNewRange(r = [0.02, 0.3], s = [-100, 100]) {
    ((this._springRotationZClampRange = r), (this._springRotationYClampRange = s));
  }
}
const bA = 0.3;
let Mv = !0;
function changeSection(t) {
  if (!events.isInClickEffect && Mv)
    switch (
      ((Mv = !1),
      Tweening.TweenManager.Timeline(bA)
        .delay(bA)
        .call(() => (Mv = !0))
        .start(),
      events.currentShowingState)
    ) {
      case ShowState.State1:
        t
          ? events.emit(events.UPDATESHOWINGSTATE, ShowState.State2)
          : events.emit(events.UPDATESHOWINGSTATE, ShowState.State4);
        break;
      case ShowState.State2:
        t
          ? events.emit(events.UPDATESHOWINGSTATE, ShowState.State3)
          : events.emit(events.UPDATESHOWINGSTATE, ShowState.State1);
        break;
      case ShowState.State3:
        t
          ? events.emit(events.UPDATESHOWINGSTATE, ShowState.State4)
          : events.emit(events.UPDATESHOWINGSTATE, ShowState.State2);
        break;
      case ShowState.State4:
        t
          ? events.emit(events.UPDATESHOWINGSTATE, ShowState.State1)
          : events.emit(events.UPDATESHOWINGSTATE, ShowState.State3);
        break;
    }
}
export {
  isMobile,
  isPortrait,
  cM,
  rl,
  TO,
  EO,
  MO,
  _A,
  yA,
  $u,
  Ev,
  Bd,
  xA,
  CO,
  OrbitController,
  bA,
  Mv,
  changeSection,
};
