import * as nt from "react";
import { ShowState, events } from "./../state/events.js";
import { isMobile } from "./../scene/orbit.js";
import { AnimatePresence as Pc, motion as oo } from "framer-motion";
import { resourceConfig } from "./../config/resources.js";
let zS = 0;
function PhotoButton() {
  const photoRef = nt.useRef(null),
    [isOpen, setOpen] = nt.useState(!1),
    [state, setState] = nt.useState(ShowState.Loading),
    [isInteracting, setInteracting] = nt.useState(!1);
  nt.useEffect(() => {
    const D = (R) => {
        setState(R);
      },
      U = (R) => {
        setInteracting(R);
      };
    return (
      events.on(events.UPDATESHOWINGSTATE, D),
      events.on(events.CLICKEFFECT, U),
      () => {
        (events.off(events.UPDATESHOWINGSTATE, D), events.off(events.CLICKEFFECT, U));
      }
    );
  }, []);
  const _ = nt.useCallback(() => {
      ((zS += 1),
        events.emit(events.SCREENSHOT),
        events.emit(events.PLAY_SFX, "ka"),
        setOpen(!0),
        (photoRef.current.style.display = "block"));
    }, []),
    A = nt.useCallback(() => {
      (events.emit(events.PLAY_SFX, "click"),
        setOpen(!1),
        (photoRef.current.style.display = "none"));
    }, []),
    m = isMobile();
  return (
    <>
      <div
        style={{
          opacity: isInteracting ? 0 : 1,
          transition: "0.2s all 0.3s",
        }}
      >
        <Pc mode="popLayout">
          {state == ShowState.State5 && (
            <oo.div
              id="screenshot"
              className="screenshot"
              initial={{
                y: -30,
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
              style={{
                backgroundColor: isOpen ? "#000d" : "",
                pointerEvents: isOpen ? "all" : "none",
                zIndex: "2",
              }}
            >
              <div
                ref={photoRef}
                style={{
                  display: "none",
                }}
              >
                <img id="screenshot-img" />
                <p>{"长按图片可保存并分享"}</p>
              </div>
              <div
                className="camera"
                style={{
                  marginBottom: m ? "" : "4rem",
                }}
              >
                {!isOpen && (
                  <img
                    src={resourceConfig.autoURL("res/icon/photo.png")}
                    alt=""
                    onClick={_}
                    style={
                      m
                        ? {}
                        : {
                            width: "2.4rem",
                          }
                    }
                  />
                )}
                {isOpen && (
                  <img
                    src={resourceConfig.autoURL("res/icon/close2.png")}
                    alt=""
                    onClick={A}
                    style={
                      m
                        ? {}
                        : {
                            width: "2.4rem",
                          }
                    }
                  />
                )}
              </div>
            </oo.div>
          )}
        </Pc>
      </div>
      <Pc mode="popLayout">
        <div className="key_Light" key={zS} />
      </Pc>
    </>
  );
}
export { zS, PhotoButton };
