/*
 * Kairos 3D lineage graph.
 *
 * The same persisted catalog edges that drive the 2D explorer are drawn here as
 * a layered left-to-right DAG: every column is one lineage hop, cards carry the
 * asset label, and curved arrows run from a dependency into its consumer.  The
 * point of the view is to make the connection legible at a glance, so the layout
 * is derived from the edge list and nothing is positioned by asset id or schema
 * name.
 */
(()=>{
  const T = window.THREE;
  if(!T) return;
  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  const CARD_W=5.6, CARD_H=1.8, PITCH_Y=2.35, LAYER_GAP=2.4, INNER_GAP=1.3, MAX_ROWS=9;
  const KIND_COLOR={source:0x2dd4bf, transform:0xa78bfa, output:0x60a5fa};
  const KIND_HEX={source:'#2dd4bf', transform:'#a78bfa', output:'#60a5fa'};
  const EDGE_BASE=0x3f7396;

  /* Longest-path layering, bounded by the node count so a cycle cannot loop. */
  function layerMap(list,edges){
    const layerById={};
    list.forEach(a=>{layerById[a.id]=0});
    for(let pass=0;pass<list.length;pass++){
      let moved=false;
      edges.forEach(e=>{
        if(layerById[e[0]]===undefined||layerById[e[1]]===undefined) return;
        const next=layerById[e[0]]+1;
        if(next>layerById[e[1]]){layerById[e[1]]=next;moved=true}
      });
      if(!moved) break;
    }
    return layerById;
  }

  /* Assets within `hops` of the selected node in either direction. */
  function neighborhood(list,edges,startId,hops){
    const allowed=new Set(list.map(a=>a.id));
    if(!startId||!allowed.has(startId)||!hops) return allowed;
    const down=new Map(),up=new Map();
    edges.forEach(e=>{
      if(!allowed.has(e[0])||!allowed.has(e[1])) return;
      if(!down.has(e[0])) down.set(e[0],[]);
      down.get(e[0]).push(e[1]);
      if(!up.has(e[1])) up.set(e[1],[]);
      up.get(e[1]).push(e[0]);
    });
    const seen=new Set([startId]);
    let frontier=[startId];
    for(let hop=0;hop<hops;hop++){
      const next=[];
      frontier.forEach(id=>{
        (down.get(id)||[]).concat(up.get(id)||[]).forEach(other=>{
          if(!seen.has(other)){seen.add(other);next.push(other)}
        });
      });
      if(!next.length) break;
      frontier=next;
    }
    return seen;
  }

  function mount({host,assets,edges,selected,mode='layered',filter='all',depth='full',onSelect=()=>{}}){
    if(!host||!T) return ()=>{};
    host.querySelectorAll('canvas[data-kairos-scene]').forEach(c=>c.remove());

    const scene=new T.Scene();
    scene.fog=new T.FogExp2(0x05080f,.005);
    const camera=new T.PerspectiveCamera(43,Math.max(1,host.clientWidth)/Math.max(1,host.clientHeight),.1,400);
    const renderer=new T.WebGLRenderer({antialias:true,alpha:false,powerPreference:'high-performance'});
    renderer.domElement.dataset.kairosScene='true';
    renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,1.75));
    renderer.setSize(host.clientWidth||720,host.clientHeight||490);
    renderer.setClearColor?.(0x05080f,1);
    renderer.outputColorSpace=T.SRGBColorSpace;
    host.prepend(renderer.domElement);

    scene.add(new T.HemisphereLight(0x9dc7ff,0x0a0f18,1.7));
    const key=new T.DirectionalLight(0xffffff,2.1); key.position.set(-14,20,26); scene.add(key);
    const rim=new T.PointLight(0x3b82f6,1.1,120,2); rim.position.set(14,-12,18); scene.add(rim);

    const root=new T.Group(); scene.add(root);
    const dataLayer=new T.Group(); root.add(dataLayer);
    const positions={};
    const nodeMeshes=[];
    const edgeMeshes=[];
    const pickables=[];
    const animated=[];

    /* ---- layout ---------------------------------------------------------- */
    const filtered=(assets||[]).filter(a=>filter==='all'||a.schema===filter);
    const hopLimit=depth==='full'||!depth?0:(Number(depth)||0);
    const visibleIds=neighborhood(filtered,edges||[],selected,hopLimit);
    const list=filtered.filter(a=>visibleIds.has(a.id));
    const visEdges=(edges||[]).filter(e=>visibleIds.has(e[0])&&visibleIds.has(e[1]));
    const layerById=list.length?layerMap(list,visEdges):{};
    const layerIds=[...new Set(Object.values(layerById))].sort((a,b)=>a-b);
    const layerGroups={};
    list.forEach(a=>{
      const layer=layerById[a.id]||0;
      (layerGroups[layer]||(layerGroups[layer]=[])).push(a);
    });
    layerIds.forEach(layer=>layerGroups[layer].sort((a,b)=>String(a.name).localeCompare(String(b.name))));
    const rowsCap=list.length<=8?8:MAX_ROWS;
    const bands=layerIds.map(layer=>{
      const group=layerGroups[layer]||[];
      const chunks=[];
      for(let i=0;i<group.length;i+=rowsCap) chunks.push(group.slice(i,i+rowsCap));
      const width=Math.max(CARD_W,chunks.length*CARD_W+(chunks.length-1)*INNER_GAP);
      return {layer,group,chunks,width,rows:chunks.reduce((m,c)=>Math.max(m,c.length),0)};
    });
    const totalW=bands.reduce((sum,b)=>sum+b.width,0)+Math.max(0,bands.length-1)*LAYER_GAP;
    let xCursor=-totalW/2;
    const bounds={minY:Infinity,maxY:-Infinity};
    bands.forEach(band=>{
      band.x0=xCursor;
      band.chunks.forEach((chunk,ci)=>{
        const cx=xCursor+ci*(CARD_W+INNER_GAP)+CARD_W/2;
        chunk.forEach((a,ri)=>{
          const y=((chunk.length-1)/2-ri)*PITCH_Y;
          positions[a.id]=new T.Vector3(cx,y,0);
          bounds.minY=Math.min(bounds.minY,y); bounds.maxY=Math.max(bounds.maxY,y);
        });
      });
      xCursor+=band.width+LAYER_GAP;
    });
    if(!Number.isFinite(bounds.minY)){bounds.minY=0;bounds.maxY=0}
    const contentH=Math.max(4,bounds.maxY-bounds.minY)+CARD_H*2;
    const contentW=Math.max(6,totalW)+CARD_W;

    /* ---- labels and cards ------------------------------------------------ */
    function makeLabel(asset){
      const canvas=document.createElement('canvas'); canvas.width=512; canvas.height=168;
      const ctx=canvas.getContext('2d');
      const accent=KIND_HEX[asset.kind]||'#93c5fd';
      ctx.fillStyle='rgba(8,13,20,.95)'; ctx.fillRect(2,2,508,164);
      ctx.strokeStyle=accent; ctx.lineWidth=4; ctx.strokeRect(3,3,506,162);
      ctx.fillStyle=accent; ctx.fillRect(3,3,12,162);
      ctx.fillStyle='#f2f6fb'; ctx.font='700 44px "Segoe UI",Arial,sans-serif';
      const name=String(asset.name||asset.path||'asset');
      ctx.fillText(name.length>24?name.slice(0,23)+'…':name,34,70);
      ctx.fillStyle='#a7b8cb'; ctx.font='26px "Segoe UI",Arial,sans-serif';
      const sub=String(asset.schema||'default')+'  ·  '+String(asset.kind||'asset');
      ctx.fillText(sub.length>44?sub.slice(0,43)+'…':sub,34,114);
      ctx.fillStyle=accent; ctx.font='700 21px "Segoe UI",Arial,sans-serif';
      ctx.fillText(String(asset.kind||'asset').toUpperCase(),34,148);
      const tex=new T.CanvasTexture(canvas); tex.colorSpace=T.SRGBColorSpace;
      const sprite=new T.Sprite(new T.SpriteMaterial({map:tex,transparent:true,depthWrite:false}));
      sprite.scale.set(CARD_W*.96,CARD_W*.96*(168/512),1);
      return sprite;
    }

    function makeBandLabel(text){
      const canvas=document.createElement('canvas'); canvas.width=256; canvas.height=64;
      const ctx=canvas.getContext('2d');
      ctx.fillStyle='#7f95ac'; ctx.font='700 28px "Segoe UI",Arial,sans-serif';
      ctx.textAlign='center'; ctx.fillText(text,128,42);
      const tex=new T.CanvasTexture(canvas); tex.colorSpace=T.SRGBColorSpace;
      const sprite=new T.Sprite(new T.SpriteMaterial({map:tex,transparent:true,depthWrite:false}));
      sprite.scale.set(4.4,1.1,1);
      return sprite;
    }

    bands.forEach((band,index)=>{
      const bandHeight=Math.max(2.4,band.rows*PITCH_Y+1.1);
      const bandMesh=new T.Mesh(
        new T.PlaneGeometry(band.width+1.1,bandHeight),
        new T.MeshBasicMaterial({color:0x0b1622,transparent:true,opacity:.55,depthWrite:false})
      );
      bandMesh.position.set(band.x0+band.width/2,(bounds.minY+bounds.maxY)/2,-.55);
      dataLayer.add(bandMesh);
      const caption=makeBandLabel(index===0?'ROOTS':'HOP '+index);
      caption.position.set(band.x0+band.width/2,(bounds.minY+bounds.maxY)/2+bandHeight/2+.75,.06);
      dataLayer.add(caption);
    });

    list.forEach(a=>{
      const pos=positions[a.id];
      const group=new T.Group(); group.position.copy(pos); group.userData.asset=a; dataLayer.add(group);
      const color=KIND_COLOR[a.kind]||KIND_COLOR.transform;
      const isSelected=a.id===selected;
      const bodyMat=new T.MeshStandardMaterial({color,roughness:.42,metalness:.22,emissive:color,emissiveIntensity:isSelected?.4:.14,transparent:true,opacity:1});
      const body=new T.Mesh(new T.BoxGeometry(CARD_W,CARD_H,.26),bodyMat);
      body.userData.asset=a; group.add(body); pickables.push(body);
      const strip=new T.Mesh(new T.BoxGeometry(.18,CARD_H,.3),new T.MeshBasicMaterial({color:0xffffff,transparent:true,opacity:.6}));
      strip.position.set(-CARD_W/2+.09,0,.02); group.add(strip);
      const halo=new T.Mesh(
        new T.TorusGeometry(1,.035,10,72),
        new T.MeshBasicMaterial({color:isSelected?0xffffff:0x5b7f9c,transparent:true,opacity:isSelected?.95:.3})
      );
      halo.scale.set(CARD_W/2+.3,CARD_H/2+.3,1); halo.position.z=-.2;
      halo.visible=isSelected; group.add(halo);
      const label=makeLabel(a); label.position.z=.2; group.add(label);
      nodeMeshes.push({id:a.id,group,body,label,halo});
    });

    /* ---- edges with directional arrowheads ------------------------------- */
    visEdges.forEach(e=>{
      const from=positions[e[0]],to=positions[e[1]];
      if(!from||!to) return;
      const start=new T.Vector3(from.x+CARD_W/2,from.y,.03);
      const end=new T.Vector3(to.x-CARD_W/2-.3,to.y,.03);
      const dx=end.x-start.x;
      const c1=new T.Vector3(start.x+dx*.45,start.y,0);
      const c2=new T.Vector3(end.x-dx*.45,end.y,0);
      const curve=new T.CubicBezierCurve3(start,c1,c2,end);
      const mat=new T.MeshStandardMaterial({color:EDGE_BASE,roughness:.3,metalness:.15,emissive:0x1d3a4d,emissiveIntensity:.7,transparent:true,opacity:.9});
      const tube=new T.Mesh(new T.TubeGeometry(curve,26,.07,8,false),mat);
      tube.userData={from:e[0],to:e[1]}; dataLayer.add(tube);
      const theta=Math.atan2(end.y-c2.y,end.x-c2.x);
      const arrow=new T.Mesh(new T.ConeGeometry(.24,.7,10),mat);
      arrow.position.set(end.x-Math.cos(theta)*.2,end.y-Math.sin(theta)*.2,.03);
      arrow.rotation.z=theta-Math.PI/2; dataLayer.add(arrow);
      const bead=new T.Mesh(new T.SphereGeometry(.13,10,8),new T.MeshBasicMaterial({color:0xbfe8ff}));
      dataLayer.add(bead);
      animated.push({bead,curve,phase:Math.random()});
      edgeMeshes.push({tube,arrow,mat,from:e[0],to:e[1]});
    });

    /* ---- camera ---------------------------------------------------------- */
    const center=new T.Vector3(0,(bounds.minY+bounds.maxY)/2,0);
    let baseRadius=24;
    const computeFit=()=>{
      const aspect=Math.max(.2,(host.clientWidth||720)/(host.clientHeight||490));
      const vFov=43*Math.PI/180;
      const byHeight=contentH/(2*Math.tan(vFov/2));
      const byWidth=contentW/(2*Math.tan(vFov/2)*aspect);
      baseRadius=Math.max(byHeight,byWidth)*1.08;
    };
    computeFit();
    const target=new T.Vector3(center.x,center.y,center.z);
    if(selected&&positions[selected]) target.copy(positions[selected]);
    let rotY=0,rotX=.12,zoom=1;
    const updateCamera=()=>{
      const r=baseRadius/zoom;
      camera.position.set(
        target.x+Math.sin(rotY)*Math.cos(rotX)*r,
        target.y+Math.sin(rotX)*r,
        target.z+Math.cos(rotY)*Math.cos(rotX)*r
      );
      camera.lookAt(target);
    };
    updateCamera();

    /* ---- interaction ----------------------------------------------------- */
    const ray=new T.Raycaster(),pointer=new T.Vector2();
    let down=false,lastX=0,lastY=0,downX=0,downY=0,dragMoved=false,suppressClick=false;
    const pointerDown=e=>{down=true;dragMoved=false;suppressClick=false;lastX=e.clientX;lastY=e.clientY;downX=e.clientX;downY=e.clientY;renderer.domElement.setPointerCapture?.(e.pointerId)};
    let hovered=null,hoverDirty=false,hoverX=0,hoverY=0;
    const updateHover=()=>{
      const rect=renderer.domElement.getBoundingClientRect();
      pointer.set((hoverX-rect.left)/rect.width*2-1,-(hoverY-rect.top)/rect.height*2+1);
      ray.setFromCamera(pointer,camera);
      const hits=ray.intersectObjects(pickables,false);
      let o=hits[0]?.object;
      while(o&&!o.userData.asset) o=o.parent;
      const next=o?.userData.asset?nodeMeshes.find(n=>n.id===o.userData.asset.id):null;
      if(next!==hovered){
        if(hovered) hovered.group.scale.setScalar(1);
        hovered=next;
        if(hovered) hovered.group.scale.setScalar(1.04);
      }
      renderer.domElement.style.cursor=hovered?'pointer':'grab';
    };
    const pointerMove=e=>{
      if(!down){hoverX=e.clientX;hoverY=e.clientY;hoverDirty=true;return}
      const dx=e.clientX-lastX,dy=e.clientY-lastY;
      if(Math.abs(e.clientX-downX)+Math.abs(e.clientY-downY)>3) dragMoved=true;
      rotY=clamp(rotY-dx*.005,-.9,.9);
      rotX=clamp(rotX+dy*.003,-.5,.8);
      lastX=e.clientX;lastY=e.clientY;
      updateCamera();
    };
    const pointerUp=()=>{if(!down)return;down=false;suppressClick=dragMoved;dragMoved=false};
    const wheel=e=>{e.preventDefault();zoom=clamp(zoom*(e.deltaY>0?.92:1.08),.55,1.75);updateCamera()};

    const focusOn=(id)=>{
      if(!positions[id]) return;
      target.copy(positions[id]);
      updateCamera();
    };

    const applyHighlights=(activeId)=>{
      if(!activeId||!positions[activeId]) return;
      const downSet=new Set(),upSet=new Set();
      const dq=[activeId];
      while(dq.length){
        const cur=dq.pop(); downSet.add(cur);
        (edges||[]).forEach(ed=>{if(ed[0]===cur&&!downSet.has(ed[1]))dq.push(ed[1])});
      }
      const uq=[activeId];
      while(uq.length){
        const cur=uq.pop(); upSet.add(cur);
        (edges||[]).forEach(ed=>{if(ed[1]===cur&&!upSet.has(ed[0]))uq.push(ed[0])});
      }
      nodeMeshes.forEach(node=>{
        const onPath=node.id===activeId||downSet.has(node.id)||upSet.has(node.id);
        const dim=onPath?1:.24;
        node.body.material.opacity=dim;
        node.label.material.opacity=dim;
        node.body.material.emissiveIntensity=node.id===activeId?.6:onPath?.34:.06;
        node.halo.visible=node.id===activeId;
        let color=0x5b7f9c,opacity=onPath?.3:.12;
        if(node.id===activeId){color=0xffffff;opacity=1}
        else if(downSet.has(node.id)){color=0xf87171;opacity=.95}
        else if(upSet.has(node.id)){color=0x22d3ee;opacity=.95}
        node.halo.material.color.setHex(color);
        node.halo.material.opacity=opacity;
        node.halo.material.needsUpdate=true;
      });
      edgeMeshes.forEach(edge=>{
        const downstream=downSet.has(edge.from)&&downSet.has(edge.to);
        const upstream=upSet.has(edge.from)&&upSet.has(edge.to);
        let color=EDGE_BASE,emissive=0x1d3a4d,opacity=downstream||upstream?.95:.16;
        if(downstream||edge.from===activeId){color=0xf87171;emissive=0xb91c1c;opacity=.95}
        else if(upstream||edge.to===activeId){color=0x22d3ee;emissive=0x0891b2;opacity=.95}
        edge.mat.color.setHex(color);
        edge.mat.emissive.setHex(emissive);
        edge.mat.opacity=opacity;
        edge.mat.needsUpdate=true;
      });
    };

    const click=e=>{
      if(suppressClick){suppressClick=false;return}
      if(dragMoved) return;
      const rect=renderer.domElement.getBoundingClientRect();
      pointer.set((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1);
      ray.setFromCamera(pointer,camera);
      const hits=ray.intersectObjects(pickables,false);
      if(!hits.length) return;
      let o=hits[0].object;
      while(o&&!o.userData.asset) o=o.parent;
      if(!o?.userData.asset) return;
      const id=o.userData.asset.id;
      focusOn(id);
      applyHighlights(id);
      onSelect(id);
    };

    const zoomIn=()=>{zoom=clamp(zoom*1.15,.55,1.75);updateCamera()};
    const zoomOut=()=>{zoom=clamp(zoom/1.15,.55,1.75);updateCamera()};
    const resetCamera=()=>{target.copy(center);rotY=0;rotX=.12;zoom=1;updateCamera()};
    const zoomInButtons=host.querySelectorAll('[data-action="zoom-in"]');
    const zoomOutButtons=host.querySelectorAll('[data-action="zoom-out"]');
    const resetButtons=host.querySelectorAll('[data-action="reset-3d"]');
    zoomInButtons.forEach(b=>b.addEventListener('click',zoomIn));
    zoomOutButtons.forEach(b=>b.addEventListener('click',zoomOut));
    resetButtons.forEach(b=>b.addEventListener('click',resetCamera));

    renderer.domElement.addEventListener('pointerdown',pointerDown);
    renderer.domElement.addEventListener('pointermove',pointerMove);
    renderer.domElement.addEventListener('pointerup',pointerUp);
    renderer.domElement.addEventListener('pointercancel',pointerUp);
    renderer.domElement.addEventListener('lostpointercapture',pointerUp);
    renderer.domElement.addEventListener('click',click);
    renderer.domElement.addEventListener('wheel',wheel,{passive:false});

    /* ---- animation ------------------------------------------------------- */
    const motionQuery=(window.matchMedia?window.matchMedia('(prefers-reduced-motion: reduce)'):{matches:false});
    const storedMotionReduced=()=>{try{return localStorage.getItem('kairos_reduceMotion')==='true'}catch(e){return false}};
    const motionReduced=()=>motionQuery.matches||storedMotionReduced();
    let elapsed=0,previousTime=performance.now(),raf=0,alive=true;
    const beadPoint=new T.Vector3();
    const animate=(now)=>{
      if(!alive) return;
      raf=requestAnimationFrame(animate);
      const frameTime=Number.isFinite(now)?now:performance.now();
      const delta=Math.min(Math.max((frameTime-previousTime)/1000,0),.05);
      previousTime=frameTime;
      if(hoverDirty&&!down){hoverDirty=false;updateHover()}
      if(!motionReduced()){
        elapsed+=delta;
        const t=elapsed*.07;
        animated.forEach(p=>{
          const u=(t+p.phase)%1;
          if(!Number.isFinite(u)) return;
          p.bead.position.copy(p.curve.getPoint(u,beadPoint));
        });
      }
      renderer.render(scene,camera);
    };
    raf=requestAnimationFrame(animate);

    const resize=()=>{
      if(!host.isConnected) return;
      renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,1.75));
      camera.aspect=Math.max(1,host.clientWidth)/Math.max(1,host.clientHeight);
      camera.updateProjectionMatrix();
      renderer.setSize(host.clientWidth,host.clientHeight);
      computeFit();
      updateCamera();
    };
    window.addEventListener('resize',resize);

    const sceneNodes=document.querySelector('#sceneNodes'),sceneEdgeCount=document.querySelector('#sceneEdges');
    if(sceneNodes) sceneNodes.textContent=list.length;
    if(sceneEdgeCount) sceneEdgeCount.textContent=visEdges.filter(e=>positions[e[0]]&&positions[e[1]]).length;
    const captionTitle=host.querySelector('.observatory-caption strong');
    if(captionTitle) captionTitle.textContent='Lineage Graph';
    const captionBody=host.querySelector('.observatory-caption p');
    if(captionBody) captionBody.textContent='Left to right: dependencies to consumers. Click a node to trace its upstream and downstream paths. Drag to orbit, scroll to zoom.';

    if(selected) applyHighlights(selected);

    return ()=>{
      alive=false;
      cancelAnimationFrame(raf);
      window.removeEventListener('resize',resize);
      renderer.domElement.removeEventListener('pointerdown',pointerDown);
      renderer.domElement.removeEventListener('pointermove',pointerMove);
      renderer.domElement.removeEventListener('pointerup',pointerUp);
      renderer.domElement.removeEventListener('pointercancel',pointerUp);
      renderer.domElement.removeEventListener('lostpointercapture',pointerUp);
      renderer.domElement.removeEventListener('click',click);
      renderer.domElement.removeEventListener('wheel',wheel);
      zoomInButtons.forEach(b=>b.removeEventListener('click',zoomIn));
      zoomOutButtons.forEach(b=>b.removeEventListener('click',zoomOut));
      resetButtons.forEach(b=>b.removeEventListener('click',resetCamera));
      scene.traverse(o=>{
        o.geometry?.dispose?.();
        if(o.material){
          if(Array.isArray(o.material)) o.material.forEach(m=>{m.map?.dispose?.();m.dispose?.()});
          else {o.material.map?.dispose?.();o.material.dispose?.()}
        }
      });
      renderer.dispose();
      /* dispose() leaves the WebGL context alive; remounting repeatedly would
         exhaust the browser's context limit and blank the view. */
      renderer.forceContextLoss?.();
      renderer.domElement.remove();
    };
  }

  window.KairosObservatory={mount};
})();
