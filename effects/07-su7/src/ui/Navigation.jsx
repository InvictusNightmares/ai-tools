import * as nt from "react";
import { ShowState, events, ColorPanelState } from "./../state/events.js";
import { AnimatePresence as Pc, motion as oo } from "framer-motion";
import { isMobile } from "./../scene/orbit.js";
import { Tweening } from "./../engine/index.js";
let cm = {
  value: !0,
};
function SectionNavigation() {
  const [state, setState] = nt.useState(ShowState.Loading),
    [isInteracting, setInteracting] = nt.useState(!1);
  return (
    nt.useEffect(() => {
      const h = (g) => {
          setState(g);
        },
        l = (g) => {
          setInteracting(g);
        };
      return (
        events.on(events.UPDATESHOWINGSTATE, h),
        events.on(events.CLICKEFFECT, l),
        () => {
          (events.off(events.UPDATESHOWINGSTATE, h), events.off(events.CLICKEFFECT, l));
        }
      );
    }, []),
    (
      <>
        <div
          className="StateTable-container"
          style={{
            opacity: isInteracting ? 0 : 1,
            transition: "0.2s all 0.3s",
          }}
        >
          <Pc mode="popLayout">
            {state != ShowState.BeginAnim && state != ShowState.Loading && (
              <oo.div
                className="StateTable-content"
                initial={{
                  x: 10,
                  opacity: 0,
                }}
                animate={{
                  x: 0,
                  opacity: 1,
                }}
                exit={{
                  x: -10,
                  opacity: 0,
                }}
                transition={{
                  duration: 0.5,
                }}
              >
                <div className="backgroundLine" />
                {HU.map((h, l) => (
                  <div
                    className="item"
                    style={{
                      backgroundColor: h == state ? "rgb(255, 146, 69)" : "",
                    }}
                    onClick={() => {
                      !events.isInClickEffect &&
                        h != state &&
                        cm.value &&
                        (h == ShowState.State5 && events.emit(events.CHANGECOLOR, "custom"),
                        isMobile() &&
                          events.emit(
                            events.UPDATECOLORTABLESTATE,
                            ColorPanelState.customColorTable,
                          ),
                        events.emit(events.UPDATESHOWINGSTATE, h),
                        events.emit(events.PLAY_SFX, "click"),
                        (cm.value = !1),
                        Tweening.TweenManager.Timeline(cm)
                          .delay(0.3)
                          .call(() => {
                            cm.value = !0;
                          })
                          .start());
                    }}
                    key={l}
                  >
                    {h == state && <div className="item-Line" />}
                    <div className="tableName">
                      <div
                        style={{
                          color: h == state ? "#fff" : "",
                          fontSize: h == state ? "0.9rem" : "",
                        }}
                      >
                        {VU[l]}
                      </div>
                    </div>
                    <div className="clickBox" />
                  </div>
                ))}
              </oo.div>
            )}
          </Pc>
        </div>
      </>
    )
  );
}
const HU = [
  ShowState.State1,
  ShowState.State2,
  ShowState.State3,
  ShowState.State4,
  ShowState.State5,
];
const VU = ["SU7", "车身", "风阻", "雷达", "定制"];
export { cm, SectionNavigation, HU, VU };
