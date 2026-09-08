import * as nt from "react";
import { ShowState, events, ColorPanelState } from "./../state/events.js";
import { resources, resourceConfig } from "./../config/resources.js";
import { AnimatePresence as Pc, motion as oo } from "framer-motion";
import { isMobile } from "./../scene/orbit.js";
import { Nh } from "./paint-slider.jsx";
let Hv = !0,
  Ud = "5px";
function CustomPaintPanel() {
  const [state, setState] = nt.useState(ShowState.Loading),
    [panel, setPanel] = nt.useState(events.currentColorTableState),
    [isInteracting, setInteracting] = nt.useState(!1),
    [colorIndex, setColorIndex] = nt.useState("0"),
    [customHsl, setCustomHsl] = nt.useState({
      ...resources.colors.get("custom").hsl,
    });
  return (
    nt.useEffect(() => {
      const D = (ce) => {
          setState(ce);
        },
        U = (ce) => {
          (setCustomHsl({
            ...resources.colors.get("custom").hsl,
          }),
            setColorIndex(ce));
        },
        R = (ce) => {
          setInteracting(ce);
        },
        ne = (ce) => {
          setPanel(ce);
        };
      return (
        events.on(events.CLICKEFFECT, R),
        events.on(events.CHANGECOLOR, U),
        events.on(events.UPDATESHOWINGSTATE, D),
        events.on(events.UPDATECOLORTABLESTATE, ne),
        () => {
          (events.off(events.CLICKEFFECT, R),
            events.off(events.CHANGECOLOR, U),
            events.off(events.UPDATESHOWINGSTATE, D),
            events.off(events.UPDATECOLORTABLESTATE, ne));
        }
      );
    }, []),
    (
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
                className="LeftCustomBar-container"
                style={{
                  left: isMobile() ? "0vmin" : "",
                  marginLeft: isMobile() ? "-1rem" : "",
                }}
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
                key={"ChangeState5Bar-left"}
              >
                <div
                  className="LeftCustomBar-content"
                  style={{
                    scale: isMobile() ? "0.7" : "",
                  }}
                >
                  <div className="LeftCustomBar-top">
                    <Pc mode="popLayout">
                      {(panel == ColorPanelState.customColorTable || !isMobile()) &&
                        colorIndex == "custom" && (
                          <oo.div
                            className="Slider-content"
                            initial={{
                              x: 30,
                              opacity: 0,
                            }}
                            animate={{
                              x: 0,
                              opacity: 1,
                            }}
                            exit={{
                              x: -30,
                              opacity: 0,
                            }}
                            transition={{
                              duration: 0.2,
                            }}
                            key={"preset"}
                          >
                            <div className="Slider-table">
                              <p>{"色相"}</p>
                              <HueSlider height={Ud} />
                            </div>
                            <div className="Slider-table">
                              <p>{"饱和度"}</p>
                              <SaturationSlider height={Ud} />
                            </div>
                            <div className="Slider-table">
                              <p>{"明度"}</p>
                              <LightnessSlider height={Ud} />
                            </div>
                            <div className="Slider-table">
                              <p>{"金属度"}</p>
                              <MetalnessSlider height={Ud} />
                            </div>
                            <div className="Slider-table">
                              <p>{"粗糙度"}</p>
                              <RoughnessSlider height={Ud} />
                            </div>
                          </oo.div>
                        )}
                      {panel == ColorPanelState.presetColorTable && isMobile() && (
                        <oo.div
                          className="Slider-content"
                          initial={{
                            x: 30,
                            opacity: 0,
                          }}
                          animate={{
                            x: 0,
                            opacity: 1,
                          }}
                          exit={{
                            x: -30,
                            opacity: 0,
                          }}
                          transition={{
                            duration: 0.2,
                          }}
                          key={"custom"}
                        >
                          <div className="Bar-table">
                            {Array.from(resources.colors.keys()).map((D, U) => {
                              if (["custom", "00", "01", "02"].includes(D))
                                return (
                                  <div
                                    className="Bar"
                                    style={{
                                      ...(D == "custom"
                                        ? {
                                            backgroundColor: `hsl(${customHsl.h * 360}, ${customHsl.s * 100}%, ${customHsl.l * 100}%)`,
                                          }
                                        : {}),
                                      backgroundImage: `url(${resourceConfig.autoURL("res/icon/" + resources.colors.get(D).bgUrl)})`,
                                    }}
                                    onClick={() => {
                                      (D != colorIndex &&
                                        (events.emit(events.CHANGECOLOR, D), setColorIndex(D)),
                                        events.emit(events.PLAY_SFX, "click"));
                                    }}
                                    key={D}
                                  >
                                    {colorIndex == D && <div className="Bar-Line" />}
                                  </div>
                                );
                            })}
                          </div>
                          <div className="Bar-table">
                            {Array.from(resources.colors.keys()).map((D, U) => {
                              if (["03", "04", "05", "06"].includes(D))
                                return (
                                  <div
                                    className="Bar"
                                    style={{
                                      ...(D == "custom"
                                        ? {
                                            backgroundColor: `hsl(${customHsl.h * 360}, ${customHsl.s * 100}%, ${customHsl.l * 100}%)`,
                                          }
                                        : {}),
                                      backgroundImage: `url(${resourceConfig.autoURL("res/icon/" + resources.colors.get(D).bgUrl)})`,
                                    }}
                                    onClick={() => {
                                      (D != colorIndex &&
                                        (events.emit(events.CHANGECOLOR, D), setColorIndex(D)),
                                        events.emit(events.PLAY_SFX, "click"));
                                    }}
                                    key={D}
                                  >
                                    {colorIndex == D && <div className="Bar-Line" />}
                                  </div>
                                );
                            })}
                          </div>
                          <div className="Bar-table">
                            {Array.from(resources.colors.keys()).map((D, U) => {
                              if (["07", "08", "09", "10"].includes(D))
                                return (
                                  <div
                                    className="Bar"
                                    style={{
                                      ...(D == "custom"
                                        ? {
                                            backgroundColor: `hsl(${customHsl.h * 360}, ${customHsl.s * 100}%, ${customHsl.l * 100}%)`,
                                          }
                                        : {}),
                                      backgroundImage: `url(${resourceConfig.autoURL("res/icon/" + resources.colors.get(D).bgUrl)})`,
                                    }}
                                    onClick={() => {
                                      (D != colorIndex &&
                                        (events.emit(events.CHANGECOLOR, D), setColorIndex(D)),
                                        events.emit(events.PLAY_SFX, "click"));
                                    }}
                                    key={D}
                                  >
                                    {colorIndex == D && <div className="Bar-Line" />}
                                  </div>
                                );
                            })}
                          </div>
                          <div className="Bar-table">
                            {Array.from(resources.colors.keys()).map((D, U) => {
                              if (["11"].includes(D))
                                return (
                                  <div
                                    className="Bar"
                                    style={{
                                      ...(D == "custom"
                                        ? {
                                            backgroundColor: `hsl(${customHsl.h * 360}, ${customHsl.s * 100}%, ${customHsl.l * 100}%)`,
                                          }
                                        : {}),
                                      backgroundImage: `url(${resourceConfig.autoURL("res/icon/" + resources.colors.get(D).bgUrl)})`,
                                    }}
                                    onClick={() => {
                                      (D != colorIndex &&
                                        (events.emit(events.CHANGECOLOR, D), setColorIndex(D)),
                                        events.emit(events.PLAY_SFX, "click"));
                                    }}
                                    key={D}
                                  >
                                    {colorIndex == D && <div className="Bar-Line" />}
                                  </div>
                                );
                            })}
                          </div>
                        </oo.div>
                      )}
                    </Pc>
                  </div>
                  {isMobile() && (
                    <div className="LeftCustomBar-bottom">
                      <img
                        src={resourceConfig.autoURL("res/icon/ChangeButton.png")}
                        alt=""
                        onClick={() => {
                          Hv &&
                            ((Hv = !1),
                            events.emit(events.PLAY_SFX, "click"),
                            setTimeout(() => {
                              Hv = !0;
                            }, 300),
                            panel == ColorPanelState.customColorTable
                              ? events.emit(
                                  events.UPDATECOLORTABLESTATE,
                                  ColorPanelState.presetColorTable,
                                )
                              : (events.emit(events.CHANGECOLOR, "custom"),
                                events.emit(
                                  events.UPDATECOLORTABLESTATE,
                                  ColorPanelState.customColorTable,
                                )));
                        }}
                      />
                    </div>
                  )}
                </div>
              </oo.div>
            )}
          </Pc>
        </div>
      </>
    )
  );
}
function HueSlider({ ...t }) {
  const [n, r] = nt.useState({
      h: 0,
      s: 0,
      v: resources.colors.get("custom").hsl.h * 100,
      a: 1,
    }),
    [s, h] = nt.useState({
      ...resources.colors.get("custom").hsl,
    });
  return (
    nt.useEffect(() => {
      const l = () => {
        h({
          ...resources.colors.get("custom").hsl,
        });
      };
      return (
        events.on(events.CHANGECOLOR, l),
        () => {
          events.off(events.CHANGECOLOR, l);
        }
      );
    }, []),
    (
      <Nh
        {...t}
        className="SliderHue"
        hsva={n}
        style={{
          borderRadius: "50%",
        }}
        radius="3px"
        backgroundGradient="hsl(0, 100%, 50%) 0%, hsl(60, 100%, 50%) 17%, hsl(120, 100%, 50%) 33%, hsl(180, 100%, 50%) 50%, hsl(240, 100%, 50%) 67%, hsl(300, 100%, 50%) 83%, hsl(0, 100%, 50%) 100%"
        onChange={(l) => {
          r({
            ...n,
            ...l,
          });
          const g = resources.colors.get("custom").col,
            _ = resources.colors.get("custom").hsl;
          ((_.h = l.v / 100),
            g.setHSL(_.h, _.s, _.l).convertSRGBToLinear(),
            resources.colors.get("custom").col.copy(g),
            events.emit(events.CHANGECOLOR, "custom"));
        }}
      />
    )
  );
}
function SaturationSlider({ ...t }) {
  const [n, r] = nt.useState({
      h: 0,
      s: 0,
      v: resources.colors.get("custom").hsl.s * 100,
      a: 1,
    }),
    [s, h] = nt.useState({
      ...resources.colors.get("custom").hsl,
    });
  return (
    nt.useEffect(() => {
      const l = () => {
        h({
          ...resources.colors.get("custom").hsl,
        });
      };
      return (
        events.on(events.CHANGECOLOR, l),
        () => {
          events.off(events.CHANGECOLOR, l);
        }
      );
    }, []),
    (
      <Nh
        {...t}
        className="SliderHue"
        hsva={n}
        style={{
          borderRadius: "50%",
        }}
        radius="3px"
        backgroundGradient={`rgb(0, 0, 0), hsl(${s.h * 360}, 100%, 50%)`}
        onChange={(l) => {
          r({
            ...n,
            ...l,
          });
          const g = resources.colors.get("custom").col,
            _ = resources.colors.get("custom").hsl;
          ((_.s = l.v / 100),
            g.setHSL(_.h, _.s, _.l).convertSRGBToLinear(),
            resources.colors.get("custom").col.copy(g),
            events.emit(events.CHANGECOLOR, "custom"));
        }}
      />
    )
  );
}
function LightnessSlider({ ...t }) {
  const [n, r] = nt.useState({
    h: 0,
    s: 0,
    v: resources.colors.get("custom").hsl.l * 100,
    a: 1,
  });
  return (
    <Nh
      {...t}
      className="SliderHue"
      hsva={n}
      style={{
        borderRadius: "50%",
      }}
      radius="3px"
      onChange={(s) => {
        r({
          ...n,
          ...s,
        });
        const h = resources.colors.get("custom").col,
          l = resources.colors.get("custom").hsl;
        ((l.l = s.v / 100),
          h.setHSL(l.h, l.s, l.l).convertSRGBToLinear(),
          resources.colors.get("custom").col.copy(h),
          events.emit(events.CHANGECOLOR, "custom"));
      }}
    />
  );
}
function MetalnessSlider({ ...t }) {
  const [n, r] = nt.useState({
    h: 0,
    s: 0,
    v: resources.colors.get("custom").metal * 100,
    a: 1,
  });
  return (
    <Nh
      {...t}
      className="SliderHue"
      hsva={n}
      style={{
        borderRadius: "50%",
      }}
      radius="3px"
      onChange={(s) => {
        (r({
          ...n,
          ...s,
        }),
          (resources.colors.get("custom").metal = s.v / 100),
          events.emit(events.CHANGECOLOR, "custom"));
      }}
    />
  );
}
function RoughnessSlider({ ...t }) {
  const [n, r] = nt.useState({
    h: 0,
    s: 0,
    v: resources.colors.get("custom").rough * 100,
    a: 1,
  });
  return (
    <Nh
      {...t}
      className="SliderHue"
      hsva={n}
      style={{
        borderRadius: "50%",
      }}
      radius="3px"
      onChange={(s) => {
        (r({
          ...n,
          ...s,
        }),
          (resources.colors.get("custom").rough = s.v / 100),
          events.emit(events.CHANGECOLOR, "custom"));
      }}
    />
  );
}
export {
  Hv,
  Ud,
  CustomPaintPanel,
  HueSlider,
  SaturationSlider,
  LightnessSlider,
  MetalnessSlider,
  RoughnessSlider,
};
