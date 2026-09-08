#ifdef USE_EMISSIVEMAP
                vec4 emissiveColor = texture2D( emissiveMap, vUv);
                // totalEmissiveRadiance *= ;
                // totalEmissiveRadiance *= emissiveColor.rgb * (step((cos(vUv2.x*10.+timer*20.)+1.),0.5)+0.);
                totalEmissiveRadiance =  emissiveColor.rgb*50.+totalEmissiveRadiance*emissiveColor.rgb * (step((cos(vUv2.x*10.+timer*20.)+1.),0.5)+0.);
            #endif
