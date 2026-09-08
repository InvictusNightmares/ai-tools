#if defined( USE_ENVMAP )

            #if defined( USE_BOX_PROJECTION )

                uniform vec4 probePos;
                uniform vec3 probeBoxMin;
                uniform vec3 probeBoxMax;

                vec3 boxProjection(vec3 nrdir, vec3 worldPos, vec3 probePos, vec3 boxMin, vec3 boxMax) {

                    vec3 tbot = boxMin - worldPos;
                    vec3 ttop = boxMax - worldPos;
                    vec3 tmax = mix(tbot, ttop, step(vec3(0), nrdir));
                    tmax /= nrdir;
                    float t = min(min(tmax.x, tmax.y), tmax.z);
                    return worldPos + nrdir * t - probePos;
                
                }
            #endif
                vec3 getIBLIrradiance( const in vec3 normal ) {

                    //添加光源
                    #if defined( ENVMAP_TYPE_CUBE_UV )

                        vec3 worldNormal = inverseTransformDirection( normal, viewMatrix );

                        #if defined( USE_BOX_PROJECTION )
                            if (probePos.w > 0.001) {
                                worldNormal = boxProjection(worldNormal, vWorldPosition, probePos.xyz, probeBoxMin.xyz, probeBoxMax.xyz);
                            }
                        #endif

                        vec4 envMapColor = textureCubeUV( envMap, worldNormal, 1. );
                        vec4 reflectColor = textureLod( blurCaptureReflectMap, worldNormal, 0.);
                            
                        return PI * mix( reflectColor.rgb, envMapColor.rgb, vEnvMapIntensity);
                    #else

                        return vec3( 0.0 );

                    #endif

                }

                vec3 getIBLRadiance( const in vec3 viewDir, const in vec3 normal, const in float roughness ) {

                    #if defined( ENVMAP_TYPE_CUBE_UV )

                        vec3 reflectVec = reflect( - viewDir, normal );

                        // Mixing the reflection with the normal is more accurate and keeps rough objects from gathering light from behind their tangent plane.
                        reflectVec = normalize( mix( reflectVec, normal, roughness * roughness) );

                        reflectVec = inverseTransformDirection( reflectVec, viewMatrix );

                    #if defined( USE_BOX_PROJECTION )
                        if (probePos.w > 0.001) {
                            reflectVec = boxProjection(reflectVec, vWorldPosition, probePos.xyz, probeBoxMin.xyz, probeBoxMax.xyz);
                        }
                    #endif

                        vec4 envMapColor = textureCubeUV( envMap, reflectVec, roughness );
                        envMapColor.rgb *= vEnvMapIntensity;

                        float lod = roughness*(1.7 - 0.7*roughness);
                        //粗糙度高的时候反射稍稍强一点
                        envMapColor.rgb += textureLod( cubeCaptureReflectMap, reflectVec, lod*6. ).rgb * (3.+roughness);

                        return envMapColor.rgb;
                    #else

                        return vec3( 0.0 );

                    #endif

                }

            #endif
