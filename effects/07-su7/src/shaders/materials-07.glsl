#include <common>
            varying vec3 reflectVec;
            varying vec3 vPosW;
            #if (!defined(USE_UV))
                #define USE_UV
            #endif
