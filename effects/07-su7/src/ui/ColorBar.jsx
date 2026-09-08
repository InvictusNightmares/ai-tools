import * as nt from "react";
import { ShowState, ColorPanelState, events } from "./../state/events.js";
import { resources, resourceConfig } from "./../config/resources.js";
import { AnimatePresence as Pc, motion as oo } from "framer-motion";
import { isMobile } from "./../scene/orbit.js";
function ColorBar() {
  const [state, setState] = nt.useState(ShowState.Loading),
    [panel, setPanel] = nt.useState(ColorPanelState.presetColorTable),
    [isInteracting, setInteracting] = nt.useState(!1),
    [g, _] = nt.useState("0"),
    [A, m] = nt.useState({
      ...resources.colors.get("custom").hsl,
    });
  return (
    nt.useEffect(() => {
      const D = (ne) => {
          setInteracting(ne);
        },
        U = (ne) => {
          (m({
            ...resources.colors.get("custom").hsl,
          }),
            _(ne));
        },
        R = (ne) => {
          setPanel(ne);
        };
      return (
        events.on(events.CLICKEFFECT, D),
        events.on(events.CHANGECOLOR, U),
        events.on(events.UPDATECOLORTABLESTATE, R),
        () => {
          (events.off(events.CLICKEFFECT, D),
            events.off(events.CHANGECOLOR, U),
            events.off(events.UPDATECOLORTABLESTATE, R));
        }
      );
    }, []),
    nt.useEffect(() => {
      const D = (U) => {
        (U != ShowState.State5 &&
          panel == ColorPanelState.customColorTable &&
          events.emit(events.UPDATECOLORTABLESTATE, ColorPanelState.presetColorTable),
          setState(U));
      };
      return (
        events.on(events.UPDATESHOWINGSTATE, D),
        () => {
          events.off(events.UPDATESHOWINGSTATE, D);
        }
      );
    }, [panel]),
    (
      <>
        <div
          style={{
            opacity: isInteracting ? 0 : 1,
            transition: "0.2s all 0.3s",
          }}
        >
          <Pc mode="popLayout">
            {state != ShowState.BeginAnim &&
              state != ShowState.Loading &&
              (!isMobile() || state != ShowState.State5) && (
                <oo.div
                  className="ColorBar-container"
                  initial={{
                    y: 30,
                    opacity: 0,
                  }}
                  animate={{
                    y: 0,
                    opacity: 1,
                  }}
                  exit={{
                    y: -30,
                    opacity: 0,
                  }}
                  transition={{
                    duration: 0.2,
                  }}
                >
                  <div className="ColorBar-content">
                    <oo.div
                      style={{
                        display: "flex",
                      }}
                      initial={{
                        y: 20,
                        opacity: 0,
                      }}
                      animate={{
                        y: 0,
                        opacity: 1,
                      }}
                      exit={{
                        y: -20,
                        opacity: 0,
                      }}
                      transition={{
                        duration: 0.2,
                      }}
                      key={"preset"}
                    >
                      {Array.from(resources.colors.keys()).map((D, U) => (
                        <div
                          className="Bar"
                          style={{
                            ...(D == "custom"
                              ? {
                                  backgroundColor: `hsl(${A.h * 360}, ${A.s * 100}%, ${A.l * 100}%)`,
                                }
                              : {}),
                            backgroundImage: `url(${resourceConfig.autoURL("res/icon/" + resources.colors.get(D).bgUrl)})`,
                          }}
                          onClick={() => {
                            (D != g && (events.emit(events.CHANGECOLOR, D), _(D)),
                              events.emit(events.PLAY_SFX, "click"));
                          }}
                          key={D}
                        >
                          {g == D && <div className="Bar-Line" />}
                        </div>
                      ))}
                    </oo.div>
                  </div>
                </oo.div>
              )}
          </Pc>
        </div>
      </>
    )
  );
}
export { ColorBar };
