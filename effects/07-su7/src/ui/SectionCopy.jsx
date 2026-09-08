import * as nt from "react";
import { ShowState, events } from "./../state/events.js";
import { isMobile } from "./../scene/orbit.js";
import { AnimatePresence as Pc, motion as oo } from "framer-motion";
import { resourceConfig } from "./../config/resources.js";
function SectionCopy() {
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
        {isMobile() ? (
          <div
            className="TopInfo-container"
            style={{
              opacity: isInteracting ? 0 : 1,
            }}
            key={"t1"}
          >
            <Pc mode="popLayout">
              {state == ShowState.State1 && (
                <oo.div
                  className="TopInfo-content"
                  initial={{
                    y: 10,
                    opacity: 0,
                  }}
                  animate={{
                    y: 0,
                    opacity: 1,
                  }}
                  exit={{
                    y: -10,
                    opacity: 0,
                  }}
                  transition={{
                    duration: 0.2,
                  }}
                  key={"s1"}
                >
                  <img
                    src={`${resourceConfig.autoURL("res/icon/xiaomi_su7.webp")}`}
                    alt=""
                    style={{
                      width: "50vmin",
                      marginTop: "10vmin",
                    }}
                  />
                  <div
                    style={{
                      marginTop: "2vmin",
                      color: "#fffb",
                      fontSize: "3vmin",
                    }}
                  >
                    {"C级高性能 生态科技轿车"}
                  </div>
                </oo.div>
              )}
              {state == ShowState.State2 && (
                <oo.div
                  className="TopInfo-content"
                  initial={{
                    y: 10,
                    opacity: 0,
                  }}
                  animate={{
                    y: 0,
                    opacity: 1,
                  }}
                  exit={{
                    y: -10,
                    opacity: 0,
                  }}
                  transition={{
                    duration: 0.2,
                  }}
                  key={"s2"}
                >
                  <div
                    style={{
                      marginTop: "6vmin",
                      color: "rgba(240, 198, 159, 1)",
                      fontSize: "3vmin",
                    }}
                  >
                    {"「外观设计」"}
                  </div>
                  <div
                    style={{
                      marginTop: "2vmin",
                      color: "#fff",
                      fontSize: "3vmin",
                    }}
                  >
                    {"优雅与速度感并存经得起时间考验的设计"}
                  </div>
                  <div
                    style={{
                      marginTop: "2vmin",
                      color: "#aaa",
                      fontSize: "2.5vmin",
                    }}
                  >
                    {"遵循「符合直觉」的美学设计理念，造就Xiaomi SU7 经典的流畅车身线条。"}
                  </div>
                  <div
                    style={{
                      marginTop: "2vmin",
                      color: "#aaa",
                      fontSize: "2.5vmin",
                    }}
                  >
                    {"富有力量的车身线条与自然舒展的车身比例，让优雅与速度相得益彰。"}
                  </div>
                </oo.div>
              )}
              {state == ShowState.State3 && (
                <oo.div
                  className="TopInfo-content"
                  initial={{
                    y: 10,
                    opacity: 0,
                  }}
                  animate={{
                    y: 0,
                    opacity: 1,
                  }}
                  exit={{
                    y: -10,
                    opacity: 0,
                  }}
                  transition={{
                    duration: 0.2,
                  }}
                  key={"s3"}
                >
                  <div
                    style={{
                      marginTop: "2vmin",
                      color: "#fff",
                      fontSize: "2.5vmin",
                    }}
                  >
                    {"出色的超低风阻系数"}
                  </div>
                  <div
                    style={{
                      marginTop: "1.2vmin",
                      color: "rgba(240, 198, 159, 1)",
                      fontSize: "5vmin",
                    }}
                  >
                    {"Cd 0.195"}
                  </div>
                  <div
                    style={{
                      marginTop: "1.2vmin",
                      color: "#fff",
                      fontSize: "2.5vmin",
                    }}
                  >
                    {"风，就是最好的设计师。"}
                  </div>
                  <div
                    style={{
                      marginTop: "1.2vmin",
                      color: "#fff",
                      fontSize: "2.5vmin",
                    }}
                  >
                    {
                      "经过 1000 次以上仿真实验和超过 300次油泥模型调整，不断寻找风道、车身曲线的最优解。"
                    }
                  </div>
                  <div
                    style={{
                      marginTop: "1.2vmin",
                      color: "#fff",
                      fontSize: "2.5vmin",
                    }}
                  >
                    {"最终达成 Cd0.195 超低风阻系数，带来难以想象的低能耗和出色续航表现。"}
                  </div>
                </oo.div>
              )}
              {state == ShowState.State4 && (
                <oo.div
                  className="TopInfo-content"
                  initial={{
                    y: 10,
                    opacity: 0,
                  }}
                  animate={{
                    y: 0,
                    opacity: 1,
                  }}
                  exit={{
                    y: -10,
                    opacity: 0,
                  }}
                  transition={{
                    duration: 0.2,
                  }}
                  key={"s4"}
                >
                  <div
                    style={{
                      marginTop: "0vmin",
                      color: "rgba(240, 198, 159, 1)",
                      fontSize: "3vmin",
                    }}
                  >
                    {"「智能驾驶」"}
                  </div>
                  <div
                    style={{
                      marginTop: "2vmin",
                      color: "#fff",
                      fontSize: "3vmin",
                    }}
                  >
                    {"隆重介绍XiaomiPilot更聪明、更安全的智能驾驶系统"}
                  </div>
                  <div
                    style={{
                      marginTop: "2vmin",
                      color: "#aaa",
                      fontSize: "2.5vmin",
                    }}
                  >
                    {
                      "搭载两颗 NVIDIA DRIVE Orin 芯片，综合算力高达 508 TOPS，感知硬件具备罕见的大范围探测能力；"
                    }
                  </div>
                  <div
                    style={{
                      marginTop: "2vmin",
                      color: "#aaa",
                      fontSize: "2.5vmin",
                    }}
                  >
                    {"在此之上，以领先行业的智能驾驶算法深度赋能小米全栈自研的全场景智能辅助驾驶。"}
                  </div>
                  <div className="addon">
                    <div
                      style={{
                        marginTop: "10vmin",
                      }}
                    >
                      <div>{"激光雷达"}</div>
                      <div
                        style={{
                          color: "rgba(255, 146, 69, 1)",
                        }}
                      >
                        {"x1"}
                      </div>
                    </div>
                    <div>
                      <div>{"高清摄像头"}</div>
                      <div
                        style={{
                          color: "rgba(255, 146, 69, 1)",
                        }}
                      >
                        {"x11"}
                      </div>
                    </div>
                    <div>
                      <div>{"毫米波雷达"}</div>
                      <div
                        style={{
                          color: "rgba(255, 146, 69, 1)",
                        }}
                      >
                        {"x3"}
                      </div>
                    </div>
                    <div>
                      <div>{"超声波雷达"}</div>
                      <div
                        style={{
                          color: "rgba(255, 146, 69, 1)",
                        }}
                      >
                        {"x12"}
                      </div>
                    </div>
                  </div>
                </oo.div>
              )}
            </Pc>
          </div>
        ) : (
          <div
            className="TopInfo-container"
            style={{
              opacity: isInteracting ? 0 : 1,
            }}
            key={"t2"}
          >
            <Pc mode="popLayout">
              {state == ShowState.State1 && (
                <oo.div
                  className="TopInfo-content"
                  initial={{
                    y: 10,
                    opacity: 0,
                  }}
                  animate={{
                    y: 0,
                    opacity: 1,
                  }}
                  exit={{
                    y: -10,
                    opacity: 0,
                  }}
                  transition={{
                    duration: 0.2,
                  }}
                  key={"s1"}
                >
                  <img
                    src={`${resourceConfig.autoURL("res/icon/xiaomi_su7.webp")}`}
                    alt=""
                    style={{
                      width: "40vmin",
                      marginTop: "10vmin",
                    }}
                  />
                  <div
                    style={{
                      marginTop: "2vmin",
                      color: "#fffb",
                      fontSize: "2vmin",
                    }}
                  >
                    {"C级高性能 生态科技轿车"}
                  </div>
                </oo.div>
              )}
              {state == ShowState.State2 && (
                <oo.div
                  className="TopInfo-content"
                  initial={{
                    y: 10,
                    opacity: 0,
                  }}
                  animate={{
                    y: 0,
                    opacity: 1,
                  }}
                  exit={{
                    y: -10,
                    opacity: 0,
                  }}
                  transition={{
                    duration: 0.2,
                  }}
                  key={"s2"}
                >
                  <div
                    style={{
                      marginTop: "6vmin",
                      color: "rgba(240, 198, 159, 1)",
                      fontSize: "2vmin",
                    }}
                  >
                    {"「外观设计」"}
                  </div>
                  <div
                    style={{
                      marginTop: "2vmin",
                      color: "#fff",
                      fontSize: "2vmin",
                    }}
                  >
                    {"优雅与速度感并存经得起时间考验的设计"}
                  </div>
                  <div
                    style={{
                      marginTop: "2vmin",
                      color: "#aaa",
                      fontSize: "1.4vmin",
                    }}
                  >
                    {"遵循「符合直觉」的美学设计理念，造就Xiaomi SU7 经典的流畅车身线条。"}
                  </div>
                  <div
                    style={{
                      marginTop: "2vmin",
                      color: "#aaa",
                      fontSize: "1.4vmin",
                    }}
                  >
                    {"富有力量的车身线条与自然舒展的车身比例，让优雅与速度相得益彰。"}
                  </div>
                </oo.div>
              )}
              {state == ShowState.State3 && (
                <oo.div
                  className="TopInfo-content"
                  initial={{
                    y: 10,
                    opacity: 0,
                  }}
                  animate={{
                    y: 0,
                    opacity: 1,
                  }}
                  exit={{
                    y: -10,
                    opacity: 0,
                  }}
                  transition={{
                    duration: 0.2,
                  }}
                  key={"s3"}
                >
                  <div
                    style={{
                      marginTop: "4vmin",
                      color: "#fff",
                      fontSize: "1.6vmin",
                    }}
                  >
                    {"出色的超低风阻系数"}
                  </div>
                  <div
                    style={{
                      marginTop: "1.2vmin",
                      color: "rgba(240, 198, 159, 1)",
                      fontSize: "4vmin",
                    }}
                  >
                    {"Cd 0.195"}
                  </div>
                  <div
                    style={{
                      marginTop: "1.2vmin",
                      color: "#fff",
                      fontSize: "1.6vmin",
                    }}
                  >
                    {"风，就是最好的设计师。"}
                  </div>
                  <div
                    style={{
                      marginTop: "1.2vmin",
                      color: "#fff",
                      fontSize: "1.6vmin",
                    }}
                  >
                    {
                      "经过 1000 次以上仿真实验和超过 300次油泥模型调整，不断寻找风道、车身曲线的最优解。"
                    }
                  </div>
                  <div
                    style={{
                      marginTop: "1.2vmin",
                      color: "#fff",
                      fontSize: "1.6vmin",
                    }}
                  >
                    {"最终达成 Cd0.195 超低风阻系数，带来难以想象的低能耗和出色续航表现。"}
                  </div>
                </oo.div>
              )}
              {state == ShowState.State4 && (
                <oo.div
                  className="TopInfo-content"
                  initial={{
                    y: 10,
                    opacity: 0,
                  }}
                  animate={{
                    y: 0,
                    opacity: 1,
                  }}
                  exit={{
                    y: -10,
                    opacity: 0,
                  }}
                  transition={{
                    duration: 0.2,
                  }}
                  key={"s4"}
                >
                  <div
                    style={{
                      marginTop: "4vmin",
                      color: "rgba(240, 198, 159, 1)",
                      fontSize: "1.8vmin",
                    }}
                  >
                    {"「智能驾驶」"}
                  </div>
                  <div
                    style={{
                      marginTop: "2vmin",
                      color: "#fff",
                      fontSize: "2vmin",
                    }}
                  >
                    {"隆重介绍XiaomiPilot更聪明、更安全的智能驾驶系统"}
                  </div>
                  <div
                    style={{
                      marginTop: "2vmin",
                      color: "#aaa",
                      fontSize: "1.4vmin",
                    }}
                  >
                    {
                      "搭载两颗 NVIDIA DRIVE Orin 芯片，综合算力高达 508 TOPS，感知硬件具备罕见的大范围探测能力；"
                    }
                  </div>
                  <div
                    style={{
                      marginTop: "2vmin",
                      color: "#aaa",
                      fontSize: "1.4vmin",
                    }}
                  >
                    {"在此之上，以领先行业的智能驾驶算法深度赋能小米全栈自研的全场景智能辅助驾驶。"}
                  </div>
                  <div
                    className="addon"
                    style={{
                      fontSize: "2vmin",
                    }}
                  >
                    <div
                      style={{
                        marginTop: "10vmin",
                      }}
                    >
                      <div>{"激光雷达"}</div>
                      <div
                        style={{
                          color: "rgba(255, 146, 69, 1)",
                        }}
                      >
                        {"x1"}
                      </div>
                    </div>
                    <div>
                      <div>{"高清摄像头"}</div>
                      <div
                        style={{
                          color: "rgba(255, 146, 69, 1)",
                        }}
                      >
                        {"x11"}
                      </div>
                    </div>
                    <div>
                      <div>{"毫米波雷达"}</div>
                      <div
                        style={{
                          color: "rgba(255, 146, 69, 1)",
                        }}
                      >
                        {"x3"}
                      </div>
                    </div>
                    <div>
                      <div>{"超声波雷达"}</div>
                      <div
                        style={{
                          color: "rgba(255, 146, 69, 1)",
                        }}
                      >
                        {"x12"}
                      </div>
                    </div>
                  </div>
                </oo.div>
              )}
            </Pc>
          </div>
        )}
      </>
    )
  );
}
export { SectionCopy };
