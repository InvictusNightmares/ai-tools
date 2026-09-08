import { $3 } from "./../engine/index.js";
import { defineField as B } from "./../engine/fields.js";
import { resources } from "./../config/resources.js";
var ShowState = ((t) => (
    (t[(t.Loading = 0)] = "Loading"),
    (t[(t.BeginAnim = 1)] = "BeginAnim"),
    (t[(t.State1 = 2)] = "State1"),
    (t[(t.State2 = 3)] = "State2"),
    (t[(t.State3 = 4)] = "State3"),
    (t[(t.State4 = 5)] = "State4"),
    (t[(t.State5 = 6)] = "State5"),
    t
  ))(ShowState || {}),
  ColorPanelState = ((t) => (
    (t[(t.presetColorTable = 0)] = "presetColorTable"),
    (t[(t.customColorTable = 1)] = "customColorTable"),
    t
  ))(ColorPanelState || {});
class ExperienceEvents extends $3 {
  constructor() {
    super(...arguments);
    B(this, "loading", 0);
    B(this, "PRELOADED", "preloaded");
    B(this, "UPDATESHOWINGSTATE", "updateShowingState");
    B(this, "CLICKEFFECT", "clickEffect");
    B(this, "CHANGECOLOR", "changeColor");
    B(this, "PLAY_SFX", "playSFX");
    B(this, "PLAY_BGM", "playBGM");
    B(this, "FADE_BGM", "fadeBGM");
    B(this, "MUTE", "mute");
    B(this, "PRESSED_STATE_CHANGED", "pressedStateChanged");
    B(this, "UPDATECOLORTABLESTATE", "updateColorTableState");
    B(this, "SCREENSHOT", "screenshot");
    B(this, "_isInClickEffect", !1);
    B(this, "_currentShowingState", 0);
    B(this, "_currentColorIndex", "00");
    B(this, "_currentColorTableState", 0);
  }
  get currentShowingState() {
    return this._currentShowingState;
  }
  get isInClickEffect() {
    return this._isInClickEffect;
  }
  get currentColorIndex() {
    return this._currentColorIndex;
  }
  get currentColorTableState() {
    return this._currentColorTableState;
  }
  reset() {
    (this.on(this.UPDATESHOWINGSTATE, (r) => {
      this._currentShowingState = r;
    }),
      this.on(this.CLICKEFFECT, (r) => {
        this._isInClickEffect = r;
      }),
      this.on(this.CHANGECOLOR, (r) => {
        ((this._currentColorIndex = r),
          r == "11"
            ? (resources.u_policeColorChange.value = 1)
            : (resources.u_policeColorChange.value = 0));
      }),
      this.on(this.UPDATECOLORTABLESTATE, (r) => {
        this._currentColorTableState = r;
      }),
      this.on(this.PRELOADED, () => {
        this.emit(this.UPDATESHOWINGSTATE, 1);
      }));
  }
}
const events = new ExperienceEvents();
export { ShowState, ColorPanelState, ExperienceEvents, events };
