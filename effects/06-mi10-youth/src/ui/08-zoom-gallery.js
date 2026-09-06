/* UI behavior: zoom-gallery. Plain source, shared classic-script scope. */
function slidendxB(_slideIndex2, _direction2, _jump2) {
  stopall();
  imgidB = _slideIndex2;
  document.getElementById("pointB1").style = "opacity:0.35";
  document.getElementById("pointB2").style = "opacity:0.35";
  document.getElementById("pointB3").style = "opacity:0.35";
  document.getElementById("pointB4").style = "opacity:0.35";
  document.getElementById("pointB5").style = "opacity:0.35";
  switch (imgidB) {
    case 1:
      document.getElementById("pointB1").style = "opacity:0.8";
      break;
    case 2:
      document.getElementById("pointB2").style = "opacity:0.8";
      break;
    case 3:
      document.getElementById("pointB3").style = "opacity:0.8";
      break;
    case 4:
      document.getElementById("pointB4").style = "opacity:0.8";
      break;
    case 5:
      document.getElementById("pointB5").style = "opacity:0.8";
      break;
  }
  if (_jump2 == 1) {
    imageB_1x.style.display = "block";
    imageB_2x.style.display = "block";
    imageB_3x.style.display = "block";
    document.getElementById("imageB_1").style.opacity = "0.5";
    document.getElementById("imageB_2").style.opacity = "0.5";
    document.getElementById("imageB_3").style.opacity = "0.5";
    document.getElementById("imageB_1").style.transition = "0s";
    document.getElementById("imageB_2").style.transition = "0s";
    document.getElementById("imageB_3").style.transition = "0s";
    switch (imgidB) {
      case 1:
        imageB_1x.style.backgroundImage = "url('./Img/images/B5.jpg')";
        imageB_2x.style.backgroundImage = "url('./Img/images/B1.jpg')";
        imageB_3x.style.backgroundImage = "url('./Img/images/B2.jpg')";
        imageB_1x.style.backgroundPosition = positionB1;
        imageB_2x.style.backgroundPosition = positionB2;
        imageB_3x.style.backgroundPosition = positionB3;
        break;
      case 2:
        imageB_1x.style.backgroundImage = "url('./Img/images/B3.jpg')";
        imageB_2x.style.backgroundImage = "url('./Img/images/B1.jpg')";
        imageB_3x.style.backgroundImage = "url('./Img/images/B2.jpg')";
        imageB_1x.style.backgroundPosition = positionB3;
        imageB_2x.style.backgroundPosition = positionB1;
        imageB_3x.style.backgroundPosition = positionB2;
        break;
      case 3:
        imageB_1x.style.backgroundImage = "url('./Img/images/B3.jpg')";
        imageB_2x.style.backgroundImage = "url('./Img/images/B4.jpg')";
        imageB_3x.style.backgroundImage = "url('./Img/images/B2.jpg')";
        imageB_1x.style.backgroundPosition = positionB2;
        imageB_2x.style.backgroundPosition = positionB3;
        imageB_3x.style.backgroundPosition = positionB1;
        break;
      case 4:
        imageB_1x.style.backgroundImage = "url('./Img/images/B3.jpg')";
        imageB_2x.style.backgroundImage = "url('./Img/images/B4.jpg')";
        imageB_3x.style.backgroundImage = "url('./Img/images/B5.jpg')";
        imageB_1x.style.backgroundPosition = positionB1;
        imageB_2x.style.backgroundPosition = positionB2;
        imageB_3x.style.backgroundPosition = positionB3;
        break;
      case 5:
        imageB_1x.style.backgroundImage = "url('./Img/images/B1.jpg')";
        imageB_2x.style.backgroundImage = "url('./Img/images/B4.jpg')";
        imageB_3x.style.backgroundImage = "url('./Img/images/B5.jpg')";
        imageB_1x.style.backgroundPosition = positionB3;
        imageB_2x.style.backgroundPosition = positionB1;
        imageB_3x.style.backgroundPosition = positionB2;
        break;
    }
    setTimeout(function () {
      document.getElementById("imageB_1").style.transition = "0.25s";
      document.getElementById("imageB_2").style.transition = "0.25s";
      document.getElementById("imageB_3").style.transition = "0.25s";
      document.getElementById("imageB_1").style.opacity = "1";
      document.getElementById("imageB_2").style.opacity = "1";
      document.getElementById("imageB_3").style.opacity = "1";
    }, 50);
  } else {
    document.getElementById("imageB_1").style.transition = "0.25s";
    document.getElementById("imageB_2").style.transition = "0.25s";
    document.getElementById("imageB_3").style.transition = "0.25s";
    switch (imgidB) {
      case 0:
        document.getElementById("imageB_1").style.backgroundPosition =
          positionB2;
        document.getElementById("imageB_2").style.backgroundPosition =
          positionB3;
        document.getElementById("imageB_3").style.backgroundPosition =
          positionB1;
        break;
      case 1:
        document.getElementById("imageB_1").style.backgroundPosition =
          positionB1;
        document.getElementById("imageB_2").style.backgroundPosition =
          positionB2;
        document.getElementById("imageB_3").style.backgroundPosition =
          positionB3;
        break;
      case 2:
        if (_direction2 == -1) {
          imageB_2x.style.display = "none";
        }
        document.getElementById("imageB_1").style.backgroundPosition =
          positionB3;
        document.getElementById("imageB_2").style.backgroundPosition =
          positionB1;
        document.getElementById("imageB_3").style.backgroundPosition =
          positionB2;
        break;
      case 3:
        if (_direction2 == 1) {
          imageB_2x.style.display = "none";
        } else {
          imageB_3x.style.display = "none";
        }
        document.getElementById("imageB_1").style.backgroundPosition =
          positionB2;
        document.getElementById("imageB_2").style.backgroundPosition =
          positionB3;
        document.getElementById("imageB_3").style.backgroundPosition =
          positionB1;
        break;
      case 4:
        if (_direction2 == 1) {
          imageB_3x.style.display = "none";
        }
        document.getElementById("imageB_1").style.backgroundPosition =
          positionB1;
        document.getElementById("imageB_2").style.backgroundPosition =
          positionB2;
        document.getElementById("imageB_3").style.backgroundPosition =
          positionB3;
        break;
      case 5:
        document.getElementById("imageB_1").style.backgroundPosition =
          positionB3;
        document.getElementById("imageB_2").style.backgroundPosition =
          positionB1;
        document.getElementById("imageB_3").style.backgroundPosition =
          positionB2;
        break;
      case 6:
        if (_direction2 == 1) {
          imageB_3x.style.display = "none";
        }
        document.getElementById("imageB_1").style.backgroundPosition =
          positionB2;
        document.getElementById("imageB_2").style.backgroundPosition =
          positionB3;
        document.getElementById("imageB_3").style.backgroundPosition =
          positionB1;
        break;
    }
    setTimeout(function () {
      imageB_1x.style.transition = "0s";
      imageB_2x.style.transition = "0s";
      imageB_3x.style.transition = "0s";
      imageB_1x.style.display = "block";
      imageB_2x.style.display = "block";
      imageB_3x.style.display = "block";
      switch (imgidB) {
        case 1:
          imageB_1x.style.backgroundImage = "url('./Img/images/B5.jpg')";
          imageB_2x.style.backgroundImage = "url('./Img/images/B1.jpg')";
          imageB_3x.style.backgroundImage = "url('./Img/images/B2.jpg')";
          imageB_1x.style.backgroundPosition = positionB1;
          imageB_2x.style.backgroundPosition = positionB2;
          imageB_3x.style.backgroundPosition = positionB3;
          break;
        case 2:
          imageB_1x.style.backgroundImage = "url('./Img/images/B3.jpg')";
          imageB_2x.style.backgroundImage = "url('./Img/images/B1.jpg')";
          imageB_3x.style.backgroundImage = "url('./Img/images/B2.jpg')";
          imageB_1x.style.backgroundPosition = positionB3;
          imageB_2x.style.backgroundPosition = positionB1;
          imageB_3x.style.backgroundPosition = positionB2;
          break;
        case 3:
          imageB_1x.style.backgroundImage = "url('./Img/images/B3.jpg')";
          imageB_2x.style.backgroundImage = "url('./Img/images/B4.jpg')";
          imageB_3x.style.backgroundImage = "url('./Img/images/B2.jpg')";
          imageB_1x.style.backgroundPosition = positionB2;
          imageB_2x.style.backgroundPosition = positionB3;
          imageB_3x.style.backgroundPosition = positionB1;
          break;
        case 4:
          imageB_1x.style.backgroundImage = "url('./Img/images/B3.jpg')";
          imageB_2x.style.backgroundImage = "url('./Img/images/B4.jpg')";
          imageB_3x.style.backgroundImage = "url('./Img/images/B5.jpg')";
          imageB_1x.style.backgroundPosition = positionB1;
          imageB_2x.style.backgroundPosition = positionB2;
          imageB_3x.style.backgroundPosition = positionB3;
          break;
        case 5:
          imageB_1x.style.backgroundImage = "url('./Img/images/B1.jpg')";
          imageB_2x.style.backgroundImage = "url('./Img/images/B4.jpg')";
          imageB_3x.style.backgroundImage = "url('./Img/images/B5.jpg')";
          imageB_1x.style.backgroundPosition = positionB3;
          imageB_2x.style.backgroundPosition = positionB1;
          imageB_3x.style.backgroundPosition = positionB2;
          break;
      }
    }, 250);
  }
}
var clientX4 = 0;
var moveact4 = 0;
var clientX4_old = 0;
var elementx4 = document.getElementById("imageB_0");
elementx4.onmousemove = function () {
  mousemove4(event);
};
elementx4.onmousedown = function () {
  onmousedown4(event);
};
elementx4.onmouseup = function () {
  onmouseup4(event);
};
elementx4.onmouseleave = function () {
  onmouseup4(event);
};
elementx4.ontouchstart = ontouchstart4;
elementx4.ontouchmove = ontouchmove4;
elementx4.ontouchend = onmouseup4;
function ontouchstart4(_event1) {
  clientX4_old = _event1.touches[0].clientX;
  document.getElementById("hot_cont").style.overflow = "hidden";
  moveact4 = 1;
}
function ontouchmove4(_event10) {
  clientX4 = _event10.touches[0].clientX;
  mousetouchmove4();
}
function onmousedown4(_event11) {
  clientX4_old = _event11.clientX;
  moveact4 = 1;
}
function mousemove4(_event12) {
  clientX4 = _event12.clientX;
  mousetouchmove4();
}
var moveend4 = 0;
function onmouseup4(_event13) {
  document.getElementById("hot_cont").style.overflow = "";
  if (moveend4 == 1) {
    switch (imgidB) {
      case 1:
        if (addxB < -50) {
          slidendxB(2);
        } else if (addxB > 50) {
          slidendxB(1);
        } else {
          slidendxB(1);
        }
        break;
      case 2:
        if (addxB < -50) {
          slidendxB(3, 1);
        } else if (addxB > 50) {
          slidendxB(1);
        } else {
          slidendxB(2);
        }
        break;
      case 3:
        if (addxB < -50) {
          slidendxB(4, 1);
        } else if (addxB > 50) {
          slidendxB(2, -1);
        } else {
          slidendxB(3);
        }
        break;
      case 4:
        if (addxB < -50) {
          slidendxB(5);
        } else if (addxB > 50) {
          slidendxB(3, -1);
        } else {
          slidendxB(4);
        }
        break;
      case 5:
        if (addxB < -50) {
          slidendxB(5);
        } else if (addxB > 50) {
          slidendxB(4, -1);
        } else {
          slidendxB(5);
        }
        break;
    }
  }
  moveact4 = 0;
  moveend4 = 0;
}
var newpositionB1 = 0;
var newpositionB2 = 0;
var newpositionB3 = 0;
var addxB = 0;
function mousetouchmove4() {
  if (moveact4 == 1) {
    moveend4 = 1;
    addxB = clientX4 - clientX4_old;
    newpositionB1 = parseFloat("-" + vid_width) + addxB + "px" + " " + "0px";
    newpositionB2 = addxB + "px" + " " + "0px";
    newpositionB3 = vid_width + addxB + "px" + " " + "0px";
    imageB_1x.style.transition = "0s";
    imageB_2x.style.transition = "0s";
    imageB_3x.style.transition = "0s";
    switch (imgidB) {
      case 1:
        document.getElementById("pointB1").style = "opacity:0.8";
        imageB_1x.style.backgroundPosition = newpositionB1;
        imageB_2x.style.backgroundPosition = newpositionB2;
        imageB_3x.style.backgroundPosition = newpositionB3;
        break;
      case 2:
        document.getElementById("pointB2").style = "opacity:0.8";
        imageB_1x.style.backgroundPosition = newpositionB3;
        imageB_2x.style.backgroundPosition = newpositionB1;
        imageB_3x.style.backgroundPosition = newpositionB2;
        break;
      case 3:
        document.getElementById("pointB3").style = "opacity:0.8";
        imageB_1x.style.backgroundPosition = newpositionB2;
        imageB_2x.style.backgroundPosition = newpositionB3;
        imageB_3x.style.backgroundPosition = newpositionB1;
        break;
      case 4:
        document.getElementById("pointB4").style = "opacity:0.8";
        imageB_1x.style.backgroundPosition = newpositionB1;
        imageB_2x.style.backgroundPosition = newpositionB2;
        imageB_3x.style.backgroundPosition = newpositionB3;
        break;
      case 5:
        document.getElementById("pointB5").style = "opacity:0.8";
        imageB_1x.style.backgroundPosition = newpositionB3;
        imageB_2x.style.backgroundPosition = newpositionB1;
        imageB_3x.style.backgroundPosition = newpositionB2;
        break;
    }
  }
}
document.getElementById("pointB1").onclick = function () {
  if (imgidB == 2) {
    slidendxB(1, -1, 0);
  } else {
    slidendxB(1, 0, 1);
  }
};
document.getElementById("pointB2").onclick = function () {
  if (imgidB == 3) {
    slidendxB(2, -1, 0);
  } else if (imgidB == 1) {
    slidendxB(2, 1, 0);
  } else {
    slidendxB(2, 0, 1);
  }
};
document.getElementById("pointB3").onclick = function () {
  if (imgidB == 4) {
    slidendxB(3, -1, 0);
  } else if (imgidB == 2) {
    slidendxB(3, 1, 0);
  } else {
    slidendxB(3, 0, 1);
  }
};
document.getElementById("pointB4").onclick = function () {
  if (imgidB == 5) {
    slidendxB(4, -1, 0);
  } else if (imgidB == 3) {
    slidendxB(4, 1, 0);
  } else {
    slidendxB(4, 0, 1);
  }
};
document.getElementById("pointB5").onclick = function () {
  if (imgidB == 4) {
    slidendxB(5, 1, 0);
  } else {
    slidendxB(5, 0, 1);
  }
};
