/* UI behavior: navigation. Plain source, shared classic-script scope. */
function funcClose(_value3) {
  switch (_value3) {
    case 1:
      funcAshow();
      uiscaleChide();
      document.getElementById("Etext3").style.display = "none";
      document.getElementById("slidebtn_BG").style.bottom = "-180px";
      try {
        iframe.contentWindow.app.fire("phone:anim_controller", false, 3);
      } catch (_value4) {}
      clearTimeout(timeoutx);
      break;
    case 2:
      funcAshow();
      try {
        iframe.contentWindow.app.fire("phone:anim_controller", false, 2);
      } catch (_value5) {}
      document.getElementById("sampleimg_box").style = "";
      document.getElementById("sampleimg_box_trans").style = "";
      document.getElementById("samplebtn_box").style = "";
      break;
    case 3:
      document.getElementById("btnB_01").style = "";
      document.getElementById("btnB_02").style = "";
      document.getElementById("btnB_03").style = "";
      document.getElementById("btnB_04").style = "";
      document.getElementById("btnB_05").style = "";
      document.getElementById("uiscaleB").style.opacity = 0;
      document.getElementById("closex").style.display = "none";
      setTimeout(function () {
        funcAshow();
        document.getElementById("uiscaleB").style.display = "none";
      }, 200);
      break;
    case 4:
      document.getElementById("Etext2").style.display = "none";
      uiscaleChide();
      funcAshow();
      try {
        iframe.contentWindow.app.fire("phone:anim_controller", false, 1);
      } catch (_value6) {}
      break;
    case 6:
      act = 2;
      document.getElementById("samplebtn_box").style.display = "block";
      document.getElementById("iframe").style.display = "block";
      document.getElementById("uiscaleD").style.opacity = "0";
      setTimeout(function () {
        document.getElementById("uiscaleD").style.display = "none";
      }, 250);
      stopall();
      document.body.style.overflow = "";
      break;
  }
}
document.getElementById("closex").onclick = function () {
  funcClose(act);
};
function funcAhide() {
  document.getElementById("uiBottom").style.display = "none";
  document.getElementById("sideL").style.display = "none";
  document.getElementById("sideR").style.display = "none";
  document.getElementById("uiscaleA").style.display = "none";
}
function funcAshow() {
  document.getElementById("uiBottom").style.display = "block";
  document.getElementById("uiscaleA").style.display = "flex";
  document.getElementById("uiscaleA").style.opacity = 0;
  document.getElementById("sideL").style.display = "block";
  document.getElementById("sideR").style.display = "block";
  document.getElementById("sideL").style.opacity = 0;
  document.getElementById("sideR").style.opacity = 0;
  document.getElementById("closex").style.display = "none";
  setTimeout(function () {
    document.getElementById("uiscaleA").style.opacity = 1;
    document.getElementById("sideL").style.opacity = 1;
    document.getElementById("sideR").style.opacity = 1;
  }, 50);
}
var xx = 0;
function TextX(_textIndex) {
  if (_textIndex == 0) {
    xx = 0;
    document.getElementById("btnC_01").style.display = "none";
    if (mode == 5 || mode == 6) {
      document.getElementById("Ctext").style.width = "calc(100% - 40px)";
    } else {
      document.getElementById("Ctext").style.width = "calc(100% - 80px)";
    }
    document.getElementById("Cline").style.display = "none";
  } else {
    xx = 1;
    if (mode == 5 || mode == 6) {
      document.getElementById("Ctext").style.width = "calc(100% - 160px)";
    } else {
      document.getElementById("Ctext").style.width = "calc(100% - 260px)";
    }
    document.getElementById("btnC_01").style.display = "block";
    document.getElementById("Cline").style.display = "block";
  }
}
var act = 0;
var timeoutx = 0;
function funcA(_sectionIndex) {
  act = _sectionIndex;
  switch (_sectionIndex) {
    case 1:
      funcAhide();
      document.getElementById("sideL_img").src = "Img/Icon_sc/btn_01_1.png";
      try {
        iframe.contentWindow.app.fire("phone:anim_controller", true, 3);
      } catch (_value7) {}
      timeoutx = setTimeout(function () {
        document.getElementById("slidebtn_BG").style.bottom = "0px";
        document.getElementById("closex").style.display = "block";
        document.getElementById("Etext3").style.display = "block";
      }, 7000);
      break;
    case 2:
      funcAhide();
      setTimeout(function () {
        document.getElementById("sampleimg_box").style.display = "block";
        document.getElementById("sampleimg_box_trans").style.opacity = "0";
      }, 300);
      setTimeout(function () {
        document.getElementById("sampleimg_box_trans").style.opacity = "1";
        document.getElementById("samplebtn_box").style.display = "block";
        document.getElementById("closex").style.display = "block";
      }, 600);
      try {
        iframe.contentWindow.app.fire("phone:anim_controller", true, 2);
      } catch (_value8) {}
      break;
    case 3:
      funcAhide();
      document.getElementById("btnA_img_01").src = "Img/Icon_sc/btn_03_1.png";
      document.getElementById("uiscaleB").style.display = "flex";
      document.getElementById("uiBottom").style.display = "block";
      setTimeout(function () {
        document.getElementById("uiscaleB").style.opacity = 1;
        document.getElementById("btnB_01").style.transform =
          "translate(0px,0px)";
        document.getElementById("btnB_02").style.transform =
          "translate(0px,0px)";
        document.getElementById("btnB_03").style.transform =
          "translate(0px,0px)";
        document.getElementById("btnB_04").style.transform =
          "translate(0px,0px)";
        document.getElementById("btnB_05").style.transform =
          "translate(0px,0px)";
        document.getElementById("closex").style.display = "block";
        funcB(bx);
      }, 100);
      break;
    case 4:
      funcAhide();
      document.getElementById("closex").style.display = "block";
      document.getElementById("Etext2").style.display = "block";
      try {
        iframe.contentWindow.app.fire("phone:anim_controller", true, 1);
      } catch (_value9) {}
      break;
    case 5:
      document.getElementById("btnA_img_03").src = "Img/Icon_sc/btn_05_1.png";
      break;
    case 6:
      document.getElementById("samplebtn_box").style.display = "";
      document.getElementById("iframe").style.display = "none";
      document.getElementById("uiscaleD").style.display = "block";
      document.getElementById("uiscaleD").style.opacity = "0";
      setTimeout(function () {
        document.getElementById("uiscaleD").style.opacity = "1";
        vidx();
        document.body.style.overflow = "auto";
      }, 100);
      document.getElementById("closex").style.display = "block";
      document.getElementById("D2").style.display = "block";
      break;
  }
}
document.getElementById("sideL").onmouseover = function () {
  mouseOverL();
};
document.getElementById("sideL").onmouseout = function () {
  mouseOutL();
};
document.getElementById("sideL").onclick = function () {
  funcA(1);
};
function mouseOverL() {
  document.getElementById("sideL_img").src = "Img/Icon_sc/btn_01_2.png";
}
function mouseOutL() {
  document.getElementById("sideL_img").src = "Img/Icon_sc/btn_01_1.png";
}
document.getElementById("sideR").onmouseover = function () {
  mouseOverR();
};
document.getElementById("sideR").onmouseout = function () {
  mouseOutR();
};
document.getElementById("sideR").onclick = function () {
  funcA(2);
};
function mouseOverR() {
  document.getElementById("sideR_img").src = "Img/Icon_sc/btn_02_2.png";
}
function mouseOutR() {
  document.getElementById("sideR_img").src = "Img/Icon_sc/btn_02_1.png";
}
document.getElementById("btnA_01").onmouseover = function () {
  mouseOverA1();
};
document.getElementById("btnA_01").onmouseout = function () {
  mouseOutA1();
};
document.getElementById("btnA_01").onclick = function () {
  funcA(3);
};
function mouseOverA1() {
  document.getElementById("btnA_img_01").src = "Img/Icon_sc/btn_03_2.png";
}
function mouseOutA1() {
  document.getElementById("btnA_img_01").src = "Img/Icon_sc/btn_03_1.png";
}
document.getElementById("btnA_02").onmouseover = function () {
  mouseOverA2();
};
document.getElementById("btnA_02").onmouseout = function () {
  mouseOutA2();
};
document.getElementById("btnA_02").onclick = function () {
  funcA(4);
};
function mouseOverA2() {
  document.getElementById("btnA_img_02").src = "Img/Icon_sc/btn_04_2.png";
}
function mouseOutA2() {
  document.getElementById("btnA_img_02").src = "Img/Icon_sc/btn_04_1.png";
}
document.getElementById("btnA_03").onmouseover = function () {
  mouseOverA3();
};
document.getElementById("btnA_03").onmouseout = function () {
  mouseOutA3();
};
document.getElementById("btnA_03").onclick = function () {
  funcA(5);
};
function mouseOverA3() {
  document.getElementById("btnA_img_03").src = "Img/Icon_sc/btn_05_2.png";
}
function mouseOutA3() {
  document.getElementById("btnA_img_03").src = "Img/Icon_sc/btn_05_1.png";
}
document.getElementById("btnC_img_01").onclick = function () {
  funcA(6);
};
document.getElementById("samplebtn_box").onclick = function () {
  funcA(6);
};
var bx = 4;
