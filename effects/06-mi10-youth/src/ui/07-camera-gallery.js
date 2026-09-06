/* UI behavior: camera-gallery. Plain source, shared classic-script scope. */
function slidendx(_slideIndex, _direction, _jump) {
  stopall();
  imgid = _slideIndex;
  document.getElementById("point1").style = "opacity:0.35";
  document.getElementById("point2").style = "opacity:0.35";
  document.getElementById("point3").style = "opacity:0.35";
  document.getElementById("point4").style = "opacity:0.35";
  document.getElementById("point5").style = "opacity:0.35";
  switch (imgid) {
    case 1:
      document.getElementById("point1").style = "opacity:0.8";
      break;
    case 2:
      document.getElementById("point2").style = "opacity:0.8";
      break;
    case 3:
      document.getElementById("point3").style = "opacity:0.8";
      break;
    case 4:
      document.getElementById("point4").style = "opacity:0.8";
      break;
    case 5:
      document.getElementById("point5").style = "opacity:0.8";
      break;
  }
  if (_jump == 1) {
    image_1x.style.display = "block";
    image_2x.style.display = "block";
    image_3x.style.display = "block";
    document.getElementById("image_1").style.opacity = "0.5";
    document.getElementById("image_2").style.opacity = "0.5";
    document.getElementById("image_3").style.opacity = "0.5";
    document.getElementById("image_1").style.transition = "0s";
    document.getElementById("image_2").style.transition = "0s";
    document.getElementById("image_3").style.transition = "0s";
    switch (imgid) {
      case 1:
        image_1x.style.backgroundImage = "url('./Img/images/A5.jpg')";
        image_2x.style.backgroundImage = "url('./Img/images/A1.jpg')";
        image_3x.style.backgroundImage = "url('./Img/images/A2.jpg')";
        image_1x.style.backgroundPosition = position1;
        image_2x.style.backgroundPosition = position2;
        image_3x.style.backgroundPosition = position3;
        break;
      case 2:
        image_1x.style.backgroundImage = "url('./Img/images/A3.jpg')";
        image_2x.style.backgroundImage = "url('./Img/images/A1.jpg')";
        image_3x.style.backgroundImage = "url('./Img/images/A2.jpg')";
        image_1x.style.backgroundPosition = position3;
        image_2x.style.backgroundPosition = position1;
        image_3x.style.backgroundPosition = position2;
        break;
      case 3:
        image_1x.style.backgroundImage = "url('./Img/images/A3.jpg')";
        image_2x.style.backgroundImage = "url('./Img/images/A4.jpg')";
        image_3x.style.backgroundImage = "url('./Img/images/A2.jpg')";
        image_1x.style.backgroundPosition = position2;
        image_2x.style.backgroundPosition = position3;
        image_3x.style.backgroundPosition = position1;
        break;
      case 4:
        image_1x.style.backgroundImage = "url('./Img/images/A3.jpg')";
        image_2x.style.backgroundImage = "url('./Img/images/A4.jpg')";
        image_3x.style.backgroundImage = "url('./Img/images/A5.jpg')";
        image_1x.style.backgroundPosition = position1;
        image_2x.style.backgroundPosition = position2;
        image_3x.style.backgroundPosition = position3;
        break;
      case 5:
        image_1x.style.backgroundImage = "url('./Img/images/A1.jpg')";
        image_2x.style.backgroundImage = "url('./Img/images/A4.jpg')";
        image_3x.style.backgroundImage = "url('./Img/images/A5.jpg')";
        image_1x.style.backgroundPosition = position3;
        image_2x.style.backgroundPosition = position1;
        image_3x.style.backgroundPosition = position2;
        break;
    }
    setTimeout(function () {
      document.getElementById("image_1").style.transition = "0.25s";
      document.getElementById("image_2").style.transition = "0.25s";
      document.getElementById("image_3").style.transition = "0.25s";
      document.getElementById("image_1").style.opacity = "1";
      document.getElementById("image_2").style.opacity = "1";
      document.getElementById("image_3").style.opacity = "1";
    }, 50);
  } else {
    document.getElementById("image_1").style.transition = "0.25s";
    document.getElementById("image_2").style.transition = "0.25s";
    document.getElementById("image_3").style.transition = "0.25s";
    switch (imgid) {
      case 0:
        document.getElementById("image_1").style.backgroundPosition = position2;
        document.getElementById("image_2").style.backgroundPosition = position3;
        document.getElementById("image_3").style.backgroundPosition = position1;
        break;
      case 1:
        document.getElementById("image_1").style.backgroundPosition = position1;
        document.getElementById("image_2").style.backgroundPosition = position2;
        document.getElementById("image_3").style.backgroundPosition = position3;
        break;
      case 2:
        if (_direction == -1) {
          image_2x.style.display = "none";
        }
        document.getElementById("image_1").style.backgroundPosition = position3;
        document.getElementById("image_2").style.backgroundPosition = position1;
        document.getElementById("image_3").style.backgroundPosition = position2;
        break;
      case 3:
        if (_direction == 1) {
          image_2x.style.display = "none";
        } else {
          image_3x.style.display = "none";
        }
        document.getElementById("image_1").style.backgroundPosition = position2;
        document.getElementById("image_2").style.backgroundPosition = position3;
        document.getElementById("image_3").style.backgroundPosition = position1;
        break;
      case 4:
        if (_direction == 1) {
          image_3x.style.display = "none";
        }
        document.getElementById("image_1").style.backgroundPosition = position1;
        document.getElementById("image_2").style.backgroundPosition = position2;
        document.getElementById("image_3").style.backgroundPosition = position3;
        break;
      case 5:
        document.getElementById("image_1").style.backgroundPosition = position3;
        document.getElementById("image_2").style.backgroundPosition = position1;
        document.getElementById("image_3").style.backgroundPosition = position2;
        break;
      case 6:
        if (_direction == 1) {
          image_3x.style.display = "none";
        }
        document.getElementById("image_1").style.backgroundPosition = position2;
        document.getElementById("image_2").style.backgroundPosition = position3;
        document.getElementById("image_3").style.backgroundPosition = position1;
        break;
    }
    setTimeout(function () {
      image_1x.style.transition = "0s";
      image_2x.style.transition = "0s";
      image_3x.style.transition = "0s";
      image_1x.style.display = "block";
      image_2x.style.display = "block";
      image_3x.style.display = "block";
      switch (imgid) {
        case 1:
          image_1x.style.backgroundImage = "url('./Img/images/A5.jpg')";
          image_2x.style.backgroundImage = "url('./Img/images/A1.jpg')";
          image_3x.style.backgroundImage = "url('./Img/images/A2.jpg')";
          image_1x.style.backgroundPosition = position1;
          image_2x.style.backgroundPosition = position2;
          image_3x.style.backgroundPosition = position3;
          break;
        case 2:
          image_1x.style.backgroundImage = "url('./Img/images/A3.jpg')";
          image_2x.style.backgroundImage = "url('./Img/images/A1.jpg')";
          image_3x.style.backgroundImage = "url('./Img/images/A2.jpg')";
          image_1x.style.backgroundPosition = position3;
          image_2x.style.backgroundPosition = position1;
          image_3x.style.backgroundPosition = position2;
          break;
        case 3:
          image_1x.style.backgroundImage = "url('./Img/images/A3.jpg')";
          image_2x.style.backgroundImage = "url('./Img/images/A4.jpg')";
          image_3x.style.backgroundImage = "url('./Img/images/A2.jpg')";
          image_1x.style.backgroundPosition = position2;
          image_2x.style.backgroundPosition = position3;
          image_3x.style.backgroundPosition = position1;
          break;
        case 4:
          image_1x.style.backgroundImage = "url('./Img/images/A3.jpg')";
          image_2x.style.backgroundImage = "url('./Img/images/A4.jpg')";
          image_3x.style.backgroundImage = "url('./Img/images/A5.jpg')";
          image_1x.style.backgroundPosition = position1;
          image_2x.style.backgroundPosition = position2;
          image_3x.style.backgroundPosition = position3;
          break;
        case 5:
          image_1x.style.backgroundImage = "url('./Img/images/A1.jpg')";
          image_2x.style.backgroundImage = "url('./Img/images/A4.jpg')";
          image_3x.style.backgroundImage = "url('./Img/images/A5.jpg')";
          image_1x.style.backgroundPosition = position3;
          image_2x.style.backgroundPosition = position1;
          image_3x.style.backgroundPosition = position2;
          break;
      }
    }, 250);
  }
}
var clientX3 = 0;
var moveact3 = 0;
var clientX3_old = 0;
var elementx3 = document.getElementById("image_0");
elementx3.onmousemove = function () {
  mousemove3(event);
};
elementx3.onmousedown = function () {
  onmousedown3(event);
};
elementx3.onmouseup = function () {
  onmouseup3(event);
};
elementx3.onmouseleave = function () {
  onmouseup3(event);
};
elementx3.ontouchstart = ontouchstart3;
elementx3.ontouchmove = ontouchmove3;
elementx3.ontouchend = onmouseup3;
function ontouchstart3(_event6) {
  clientX3_old = _event6.touches[0].clientX;
  document.getElementById("hot_cont").style.overflow = "hidden";
  moveact3 = 1;
}
function ontouchmove3(_event7) {
  clientX3 = _event7.touches[0].clientX;
  mousetouchmove3();
}
function onmousedown3(_event8) {
  clientX3_old = _event8.clientX;
  moveact3 = 1;
}
function mousemove3(_event9) {
  clientX3 = _event9.clientX;
  mousetouchmove3();
}
var moveend = 0;
function onmouseup3(_event0) {
  document.getElementById("hot_cont").style.overflow = "";
  if (moveend == 1) {
    switch (imgid) {
      case 1:
        if (addx < -50) {
          slidendx(2);
        } else if (addx > 50) {
          slidendx(1);
        } else {
          slidendx(1);
        }
        break;
      case 2:
        if (addx < -50) {
          slidendx(3, 1);
        } else if (addx > 50) {
          slidendx(1);
        } else {
          slidendx(2);
        }
        break;
      case 3:
        if (addx < -50) {
          slidendx(4, 1);
        } else if (addx > 50) {
          slidendx(2, -1);
        } else {
          slidendx(3);
        }
        break;
      case 4:
        if (addx < -50) {
          slidendx(5);
        } else if (addx > 50) {
          slidendx(3, -1);
        } else {
          slidendx(4);
        }
        break;
      case 5:
        if (addx < -50) {
          slidendx(5);
        } else if (addx > 50) {
          slidendx(4, -1);
        } else {
          slidendx(5);
        }
        break;
    }
  }
  moveact3 = 0;
  moveend = 0;
}
var newposition1 = 0;
var newposition2 = 0;
var newposition3 = 0;
var addx = 0;
function mousetouchmove3() {
  if (moveact3 == 1) {
    moveend = 1;
    addx = clientX3 - clientX3_old;
    newposition1 = parseFloat("-" + vid_width) + addx + "px" + " " + "0px";
    newposition2 = addx + "px" + " " + "0px";
    newposition3 = vid_width + addx + "px" + " " + "0px";
    image_1x.style.transition = "0s";
    image_2x.style.transition = "0s";
    image_3x.style.transition = "0s";
    switch (imgid) {
      case 1:
        document.getElementById("point1").style = "opacity:0.8";
        image_1x.style.backgroundPosition = newposition1;
        image_2x.style.backgroundPosition = newposition2;
        image_3x.style.backgroundPosition = newposition3;
        break;
      case 2:
        document.getElementById("point2").style = "opacity:0.8";
        image_1x.style.backgroundPosition = newposition3;
        image_2x.style.backgroundPosition = newposition1;
        image_3x.style.backgroundPosition = newposition2;
        break;
      case 3:
        document.getElementById("point3").style = "opacity:0.8";
        image_1x.style.backgroundPosition = newposition2;
        image_2x.style.backgroundPosition = newposition3;
        image_3x.style.backgroundPosition = newposition1;
        break;
      case 4:
        document.getElementById("point4").style = "opacity:0.8";
        image_1x.style.backgroundPosition = newposition1;
        image_2x.style.backgroundPosition = newposition2;
        image_3x.style.backgroundPosition = newposition3;
        break;
      case 5:
        document.getElementById("point5").style = "opacity:0.8";
        image_1x.style.backgroundPosition = newposition3;
        image_2x.style.backgroundPosition = newposition1;
        image_3x.style.backgroundPosition = newposition2;
        break;
    }
  }
}
document.getElementById("point1").onclick = function () {
  if (imgid == 2) {
    slidendx(1, -1, 0);
  } else {
    slidendx(1, 0, 1);
  }
};
document.getElementById("point2").onclick = function () {
  if (imgid == 3) {
    slidendx(2, -1, 0);
  } else if (imgid == 1) {
    slidendx(2, 1, 0);
  } else {
    slidendx(2, 0, 1);
  }
};
document.getElementById("point3").onclick = function () {
  if (imgid == 4) {
    slidendx(3, -1, 0);
  } else if (imgid == 2) {
    slidendx(3, 1, 0);
  } else {
    slidendx(3, 0, 1);
  }
};
document.getElementById("point4").onclick = function () {
  if (imgid == 5) {
    slidendx(4, -1, 0);
  } else if (imgid == 3) {
    slidendx(4, 1, 0);
  } else {
    slidendx(4, 0, 1);
  }
};
document.getElementById("point5").onclick = function () {
  if (imgid == 4) {
    slidendx(5, 1, 0);
  } else {
    slidendx(5, 0, 1);
  }
};
