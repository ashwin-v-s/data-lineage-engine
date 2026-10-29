(()=> {
  const T = window.THREE;
  if (!T) return;
  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  function mount({host,assets,edges,selected,mode='overview',filter='all',onSelect=()=>{}}){
    if(!host || !T) return ()=>{};
    host.querySelectorAll('canvas[data-kairos-scene]').forEach(c=>c.remove());
    const scene=new T.Scene();
    const skyCanvas = document.createElement('canvas'); skyCanvas.width=2; skyCanvas.height=512;
    const skyCtx = skyCanvas.getContext('2d');
    const skyGrad = skyCtx.createLinearGradient(0,0,0,512);
    skyGrad.addColorStop(0, '#1e4877'); skyGrad.addColorStop(0.5, '#4a8fe7');
    skyGrad.addColorStop(0.7, '#d8e5f2'); skyGrad.addColorStop(1, '#a8b6c4');
    skyCtx.fillStyle=skyGrad; skyCtx.fillRect(0,0,2,512);
    const skyTex=new T.CanvasTexture(skyCanvas); skyTex.colorSpace=T.SRGBColorSpace;
    scene.background=skyTex; scene.fog=new T.FogExp2(0xd8e5f2,.015);
    const camera=new T.PerspectiveCamera(43,Math.max(1,host.clientWidth)/Math.max(1,host.clientHeight),.1,180);
    camera.position.set(0,13,26);
    const renderer=new T.WebGLRenderer({antialias:true,alpha:false,powerPreference:'high-performance'});
    renderer.domElement.dataset.kairosScene='true'; renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,1.75)); renderer.setSize(host.clientWidth||720,host.clientHeight||490);
    renderer.outputColorSpace=T.SRGBColorSpace; renderer.toneMapping=T.ACESFilmicToneMapping; renderer.toneMappingExposure=1.1; renderer.shadowMap.enabled=true; renderer.shadowMap.type=T.PCFSoftShadowMap;
    host.prepend(renderer.domElement);
    scene.add(new T.HemisphereLight(0xffffff,0xa8b6c4,1.8));
    const sun=new T.DirectionalLight(0xfff5e6,4.5); sun.position.set(-20,40,30); sun.castShadow=true;
    sun.shadow.mapSize.set(2048,2048); sun.shadow.camera.left=-35; sun.shadow.camera.right=35;
    sun.shadow.camera.top=35; sun.shadow.camera.bottom=-35; sun.shadow.camera.near=10; sun.shadow.camera.far=120; sun.shadow.bias=-0.0005;
    scene.add(sun);
    const bounce=new T.PointLight(0xd8e5f2,2.0,50,2); bounce.position.set(10,5,-10); scene.add(bounce);
    const root=new T.Group();scene.add(root); const structure=new T.Group();root.add(structure);const dataLayer=new T.Group();root.add(dataLayer);
    const mats={
      floor:new T.MeshPhysicalMaterial({color:0xe6e4df,roughness:0.18,metalness:0.05,clearcoat:0.3,clearcoatRoughness:0.2}),
      wall:new T.MeshPhysicalMaterial({color:0xfaf9f5,roughness:0.6,metalness:0.05}),
      dark:new T.MeshStandardMaterial({color:0x222222,roughness:0.7,metalness:0.4}),
      glass:new T.MeshPhysicalMaterial({color:0xffffff,roughness:0.05,metalness:0.1,transmission:0.95,ior:1.5,thickness:0.2}),
      trim:new T.MeshStandardMaterial({color:0x888888,roughness:0.3,metalness:0.8}),
      grass:new T.MeshStandardMaterial({color:0x5e7c48,roughness:1.0}),
      source:new T.MeshPhysicalMaterial({color:0x20c997,roughness:0.15,metalness:0.3,clearcoat:1.0,emissive:0x20c997,emissiveIntensity:0.2}),
      transform:new T.MeshPhysicalMaterial({color:0x845ef7,roughness:0.15,metalness:0.3,clearcoat:1.0,emissive:0x845ef7,emissiveIntensity:0.2}),
      output:new T.MeshPhysicalMaterial({color:0x339af0,roughness:0.15,metalness:0.3,clearcoat:1.0,emissive:0x339af0,emissiveIntensity:0.2})
    };
    function box(parent,x,y,z,w,h,d,mat){const m=new T.Mesh(new T.BoxGeometry(w,h,d),mat);m.position.set(x,y,z);m.castShadow=true;m.receiveShadow=true;parent.add(m);return m}
    function line(parent,pts,color=0x7ca7a6,opacity=.48){const g=new T.BufferGeometry().setFromPoints(pts.map(p=>new T.Vector3(...p)));const m=new T.Line(g,new T.LineBasicMaterial({color,transparent:true,opacity}));parent.add(m);return m}
    box(structure,0,-1.25,0,50,.5,35,mats.floor);
    box(structure,0,-1.3,-22.5,60,.4,10,mats.grass);
    box(structure,0,-1.3,22.5,60,.4,10,mats.grass);
    const pool=new T.Mesh(new T.PlaneGeometry(28,12), new T.MeshPhysicalMaterial({color:0x005577, transmission:0.95, opacity:1, metalness:0.1, roughness:0.02, ior:1.33, thickness:1.5}));
    pool.rotation.x=-Math.PI/2; pool.position.set(0,-0.99, -10); structure.add(pool);
    box(structure,0,-1.15,-10,28.2,.1,12.2, mats.dark);
    for(let x=-22; x<=22; x+=11) box(structure,x,4,-18, 1.2,10.5,1.2, mats.wall);
    for(let x=-22; x<=22; x+=11) box(structure,x,9.4,0, 0.4,0.4,36, mats.trim);
    const canopy=new T.Mesh(new T.PlaneGeometry(46,36), mats.glass);
    canopy.rotation.x=-Math.PI/2; canopy.position.set(0,9.6,0); structure.add(canopy);
    const med=new T.Mesh(new T.CylinderGeometry(5.5,5.5,.15,64),new T.MeshStandardMaterial({color:0xffffff,roughness:0.2,metalness:0.1}));
    med.position.set(0,-0.92,0); med.receiveShadow=true; structure.add(med);
    for(const r of [4.0,4.8]){const ring=new T.Mesh(new T.TorusGeometry(r,.03,16,100),mats.trim);ring.rotation.x=Math.PI/2;ring.position.y=-0.8;ring.receiveShadow=true;structure.add(ring)}
    const filtered=assets.filter(a=>filter==='all'||a.schema===filter);
    const positions={},nodeMeshes=[],animated=[],edgeMeshes=[];
    const schemas=[...new Set(filtered.map(a=>String(a.schema||'default')))];const clusters=Object.fromEntries(schemas.map((schema,i)=>{const angle=i/Math.max(1,schemas.length)*Math.PI*2;return[schema,[Math.cos(angle)*8,Math.sin(angle)*6]]}));
    // Derive lineage layers from the actual edge list; asset IDs and schema names are never assumed.
    const layerById=Object.fromEntries(filtered.map(a=>[a.id,0]));for(let pass=0;pass<filtered.length;pass++){let changed=false;edges.forEach(e=>{if(layerById[e[0]]!==undefined&&layerById[e[1]]!==undefined){const next=layerById[e[0]]+1;if(next>layerById[e[1]]){layerById[e[1]]=next;changed=true}}});if(!changed)break}const layerGroups={};filtered.forEach(a=>{const layer=layerById[a.id]||0;(layerGroups[layer]||(layerGroups[layer]=[])).push(a)});const maxLayer=Math.max(0,...Object.keys(layerGroups).map(Number));
    filtered.forEach((a,i)=>{
      let x,z;
      if(mode==='lineage'){const layer=layerById[a.id]||0,group=layerGroups[layer]||[a],index=group.findIndex(item=>item.id===a.id);x=maxLayer===0?0:-12+(layer/maxLayer)*24;z=(index-(group.length-1)/2)*3.4}
      else if(mode==='clusters'){const c=clusters[String(a.schema||'default')]||[0,0],schemaItems=filtered.filter(item=>String(item.schema||'default')===String(a.schema||'default')),index=schemaItems.findIndex(item=>item.id===a.id);x=c[0]+Math.cos(index*2.4)*1.6;z=c[1]+Math.sin(index*2.4)*1.6}
      else {const ang=i/Math.max(1,filtered.length)*Math.PI*2;x=Math.cos(ang)*9.3;z=Math.sin(ang)*6.6}
      const y=.35+(i%3)*.15;positions[a.id]=new T.Vector3(x,y,z);
      // Each asset is a compact physical-looking instrument/server plinth, not a floating sphere.
      const group=new T.Group();group.position.copy(positions[a.id]);group.scale.setScalar(1.12);dataLayer.add(group);
      const colorMat=mats[a.kind]||mats.transform;
      box(group,0,-.12,0,1.65,.2,1.12,mats.dark);
      box(group,0,.13,0,1.42,.42,.94,colorMat);
      box(group,0,.37,0,1.12,.055,.72,mats.trim);
      for(let k=-1;k<=1;k++){const led=new T.Mesh(new T.SphereGeometry(.045,10,8),new T.MeshBasicMaterial({color:a.kind==='source'?0x9cebd2:a.kind==='output'?0xa8d3ff:0xd2c3ff}));led.position.set(k*.22,.42,.39);group.add(led)}
      const halo=new T.Mesh(new T.TorusGeometry(a.id===selected?1.05:.84,.018,6,48),new T.MeshBasicMaterial({color:a.id===selected?0xf0d6a2:0x8da6a0,transparent:true,opacity:a.id===selected?.95:.42}));halo.rotation.x=Math.PI/2;halo.position.y=-.03;group.add(halo);
      group.userData.asset=a;nodeMeshes.push(group);
      const canvas=document.createElement('canvas');canvas.width=512;canvas.height=128;const ctx=canvas.getContext('2d');
      ctx.fillStyle='rgba(17,27,32,.94)';ctx.fillRect(5,5,502,118);ctx.strokeStyle=a.id===selected?'#e7d2a7':'#687d7c';ctx.lineWidth=2;ctx.strokeRect(6,6,500,116);
      ctx.fillStyle='#f1f1e9';ctx.font='600 29px Arial';ctx.fillText(a.name.length>25?a.name.slice(0,24)+'…':a.name,22,49);
      ctx.fillStyle='#b7c4bd';ctx.font='22px Arial';ctx.fillText(a.schema+'  /  '+a.kind,22,83);
      const tex=new T.CanvasTexture(canvas);tex.colorSpace=T.SRGBColorSpace;
      const sprite=new T.Sprite(new T.SpriteMaterial({map:tex,transparent:true,depthTest:false}));sprite.position.set(x,1.55,z);sprite.scale.set(3.75,.94,1);dataLayer.add(sprite);
    });
    // Structural conduit lines are routed through low, tidy waypoints; particles move along real relationships.
    edges.forEach(e=>{const from=positions[e[0]],to=positions[e[1]];if(!from||!to)return;
      const distance = from.distanceTo(to);
      const arcHeight = Math.max(from.y, to.y) + distance * 0.25 + 0.8;
      const mid1=new T.Vector3(from.x + (to.x-from.x)*0.33, arcHeight, from.z + (to.z-from.z)*0.33);
      const mid2=new T.Vector3(from.x + (to.x-from.x)*0.66, arcHeight, from.z + (to.z-from.z)*0.66);
      const curve=new T.CatmullRomCurve3([from.clone().add(new T.Vector3(0,.2,0)),mid1,mid2,to.clone().add(new T.Vector3(0,.2,0))]);
      const tube=new T.Mesh(new T.TubeGeometry(curve,32,.06,8,false),new T.MeshStandardMaterial({color:0x3b82f6,metalness:.2,roughness:.2,emissive:0x2563eb,emissiveIntensity:0.6,transparent:true,opacity:.75}));tube.userData={from:e[0],to:e[1]};edgeMeshes.push(tube);dataLayer.add(tube);
      const bead=new T.Mesh(new T.SphereGeometry(.15,12,12),new T.MeshBasicMaterial({color:0xffffff}));dataLayer.add(bead);animated.push({bead,curve,phase:Math.random()});
    });
    // Custom 3D Rendered Model: Kairos Data Core Monolith & Holographic Pulsar Rings
    const coreGroup = new T.Group();
    coreGroup.position.set(0, 1.2, 0);
    structure.add(coreGroup);

    // Central Monolith Pillar
    const monolithGeo = new T.BoxGeometry(1.4, 4.2, 1.4);
    const monolithMat = new T.MeshStandardMaterial({color: 0x1f2937, roughness: 0.2, metalness: 0.85, emissive: 0x0f172a, emissiveIntensity: 0.6});
    const monolith = new T.Mesh(monolithGeo, monolithMat);
    monolith.castShadow = true;
    monolith.receiveShadow = true;
    coreGroup.add(monolith);

    // Glowing vertical energy runed fins on monolith
    for(let a=0; a<4; a++) {
      const angle = (a / 4) * Math.PI * 2;
      const fin = new T.Mesh(new T.BoxGeometry(0.08, 3.8, 0.4), new T.MeshBasicMaterial({color: 0x5eead4}));
      fin.position.set(Math.cos(angle) * 0.74, 0, Math.sin(angle) * 0.74);
      fin.rotation.y = -angle;
      coreGroup.add(fin);
    }

    // Floating Pulsar Rings
    const rings = [];
    for(let r=0; r<3; r++) {
      const radius = 2.2 + r * 0.75;
      const ringGeo = new T.TorusGeometry(radius, 0.04, 16, 100);
      const ringMat = new T.MeshBasicMaterial({color: r===0? 0x38bdf8 : r===1? 0x00ff9c : 0xa855f7, transparent: true, opacity: 0.75});
      const ringMesh = new T.Mesh(ringGeo, ringMat);
      ringMesh.rotation.x = Math.PI / 2 + (r * 0.2);
      ringMesh.position.y = -0.5 + (r * 0.6);
      coreGroup.add(ringMesh);
      rings.push({mesh: ringMesh, speed: (r % 2 === 0 ? 1 : -1) * (0.42 + r * 0.18)});
    }

    // Floating Data Crystal Orbiters
    const crystalGeo = new T.OctahedronGeometry(0.32, 0);
    const crystalMat = new T.MeshStandardMaterial({color: 0x00ff9c, roughness: 0.1, metalness: 0.9, emissive: 0x00ff9c, emissiveIntensity: 0.8});
    const crystals = [];
    for(let c=0; c<5; c++) {
      const crystal = new T.Mesh(crystalGeo, crystalMat);
      const angle = (c / 5) * Math.PI * 2;
      crystals.push({mesh: crystal, angle, dist: 3.8 + (c % 2 * 0.8), speed: 0.65 + (c * 0.12), height: (c % 2 === 0 ? 0.8 : -0.6)});
      coreGroup.add(crystal);
    }
    // Background architectural consoles removed for bright daylit plaza.
    const ray=new T.Raycaster(),pointer=new T.Vector2();let down=false,lastX=0,lastY=0,rotY=0,rotX=.1,zoom=1,target=new T.Vector3(0,0,0),raf=0,alive=true,dragMoved=false;
    const updateCamera=()=>{const radius=23/zoom;camera.position.set(target.x+Math.sin(rotY)*radius,target.y+Math.max(-.1,Math.cos(rotX)*radius*.43),target.z+Math.cos(rotY)*radius);camera.lookAt(target)};
    updateCamera();
    const pointerDown=e=>{down=true;dragMoved=false;lastX=e.clientX;lastY=e.clientY;host.setPointerCapture?.(e.pointerId)};
    let hovered=null;const pointerMove=e=>{if(!down){const rect=renderer.domElement.getBoundingClientRect();pointer.set((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1);ray.setFromCamera(pointer,camera);const hits=ray.intersectObjects(nodeMeshes,true);let o=hits[0]?.object;while(o&&!o.userData.asset)o=o.parent;const next=o?.userData.asset?o:null;if(next!==hovered){if(hovered)hovered.scale.setScalar(1.12);hovered=next;if(hovered)hovered.scale.setScalar(1.18)}renderer.domElement.style.cursor=hovered?'pointer':'grab';return}const dx=e.clientX-lastX,dy=e.clientY-lastY;if(Math.abs(dx)+Math.abs(dy)>2)dragMoved=true;rotY-=dx*.005;rotX=clamp(rotX+dy*.003,-.5,1.0);lastX=e.clientX;lastY=e.clientY;updateCamera()};
    const pointerUp=()=>{down=false};
    const wheel=e=>{zoom=clamp(zoom*(e.deltaY>0?.92:1.08),.55,1.75);updateCamera()};
    const click=e=>{if(dragMoved)return;const rect=renderer.domElement.getBoundingClientRect();pointer.set((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1);ray.setFromCamera(pointer,camera);const hits=ray.intersectObjects(nodeMeshes,true);if(hits.length){let o=hits[0].object;while(o&&!o.userData.asset)o=o.parent;if(o?.userData.asset){const id=o.userData.asset.id;if(positions[id])target.copy(positions[id]);const downSet=new Set(), upSet=new Set();const dq=[id]; while(dq.length){const cur=dq.pop();downSet.add(cur);edges.filter(ed=>ed[0]===cur).forEach(ed=>{if(!downSet.has(ed[1]))dq.push(ed[1])});} const uq=[id]; while(uq.length){const cur=uq.pop();upSet.add(cur);edges.filter(ed=>ed[1]===cur).forEach(ed=>{if(!upSet.has(ed[0]))uq.push(ed[0])});} nodeMeshes.forEach(n=>{const h=n.children.find(c=>c.geometry?.type==='TorusGeometry');if(h){const nid=n.userData.asset.id;let c=0x223344,op=0.15;if(nid===id){c=0xffffff;op=1.0}else if(downSet.has(nid)){c=0xff3333;op=0.9}else if(upSet.has(nid)){c=0x3388ff;op=0.9} h.material.color.setHex(c);h.material.opacity=op;h.material.needsUpdate=true}}); edgeMeshes.forEach(t=>{const f=t.userData.from,to=t.userData.to;let c=0x223344,em=0x000000,op=0.15;if(downSet.has(f)&&downSet.has(to)){c=0xff3333;em=0xff0000;op=0.9;}else if(upSet.has(f)&&upSet.has(to)){c=0x3388ff;em=0x0055ff;op=0.9;} t.material.color.setHex(c);t.material.emissive.setHex(em);t.material.opacity=op;t.material.needsUpdate=true});updateCamera();onSelect(id)}}};
    const zoomIn=()=>{zoom=clamp(zoom*1.15,.55,1.75);updateCamera()},zoomOut=()=>{zoom=clamp(zoom/1.15,.55,1.75);updateCamera()},resetCamera=()=>{target.set(0,0,0);rotY=0;rotX=.1;zoom=1;updateCamera()};
    const zoomInButtons=host.querySelectorAll('[data-action="zoom-in"]'),zoomOutButtons=host.querySelectorAll('[data-action="zoom-out"]'),resetButtons=host.querySelectorAll('[data-action="reset-3d"]');zoomInButtons.forEach(b=>b.addEventListener('click',zoomIn));zoomOutButtons.forEach(b=>b.addEventListener('click',zoomOut));resetButtons.forEach(b=>b.addEventListener('click',resetCamera));
    renderer.domElement.addEventListener('pointerdown',pointerDown);renderer.domElement.addEventListener('pointermove',pointerMove);renderer.domElement.addEventListener('pointerup',pointerUp);renderer.domElement.addEventListener('pointercancel',pointerUp);renderer.domElement.addEventListener('click',click);renderer.domElement.addEventListener('wheel',wheel,{passive:true});
    const motionQuery=window.matchMedia('(prefers-reduced-motion: reduce)');const motionReduced=()=>motionQuery.matches||localStorage.getItem('kairos_reduceMotion')==='true';let elapsed=0,previousTime=performance.now();const animate=(now)=>{if(!alive)return;raf=requestAnimationFrame(animate);const delta=Math.min(Math.max((now-previousTime)/1000,0),0.05);previousTime=now;if(!motionReduced()){elapsed+=delta;const t=elapsed*0.08;animated.forEach(p=>{const q=p.curve.getPoint((t+p.phase)%1);p.bead.position.copy(q)});if(coreGroup){coreGroup.rotation.y+=delta*0.30;rings.forEach(r=>{r.mesh.rotation.z+=delta*r.speed});crystals.forEach(c=>{c.angle+=delta*c.speed;c.mesh.position.x=Math.cos(c.angle)*c.dist;c.mesh.position.z=Math.sin(c.angle)*c.dist;c.mesh.position.y=c.height+Math.sin(elapsed*2+c.angle)*0.2;c.mesh.rotation.x+=delta*1.2;c.mesh.rotation.y+=delta*1.8})}}renderer.render(scene,camera)};
    animate();
    const resize=()=>{if(!host.isConnected)return;camera.aspect=Math.max(1,host.clientWidth)/Math.max(1,host.clientHeight);camera.updateProjectionMatrix();renderer.setSize(host.clientWidth,host.clientHeight)};
    window.addEventListener('resize',resize);
    const n=document.querySelector('#sceneNodes'),ed=document.querySelector('#sceneEdges');if(n)n.textContent=filtered.length;if(ed)ed.textContent=edges.filter(e=>positions[e[0]]&&positions[e[1]]).length;
    const roomTitle=host.querySelector('.observatory-caption strong');if(roomTitle)roomTitle.textContent=mode==='lineage'?'Lineage Map (Updated v4)':mode==='clusters'?'Cluster Laboratory (Updated v4)':'Central Observatory (Updated v4)';
    
    /* Selection cascade highlighting: upstream (blue) + downstream (cyan) */
    let currentSelected = selected;
    const applyHighlights=(activeId)=>{
      if(!activeId) return;
      const downSet=new Set(),upSet=new Set();
      const dq=[activeId];while(dq.length){const cur=dq.pop();downSet.add(cur);edges.filter(ed=>ed[0]===cur).forEach(ed=>{if(!downSet.has(ed[1]))dq.push(ed[1])})};
      const uq=[activeId];while(uq.length){const cur=uq.pop();upSet.add(cur);edges.filter(ed=>ed[1]===cur).forEach(ed=>{if(!upSet.has(ed[0]))uq.push(ed[0])})};
      nodeMeshes.forEach(n=>{const h=n.children.find(c=>c.geometry?.type==='TorusGeometry');if(h){const nid=n.userData.asset.id;let c=0x8da6a0,op=0.42;if(nid===activeId){c=0xffffff;op=1.0}else if(downSet.has(nid)){c=0xef4444;op=0.9}else if(upSet.has(nid)){c=0x06b6d4;op=0.9}h.material.color.setHex(c);h.material.opacity=op;h.material.needsUpdate=true}});
      edgeMeshes.forEach(t=>{const f=t.userData.from,to=t.userData.to;let c=0x3b82f6,em=0x2563eb,op=0.25;if((downSet.has(f)&&downSet.has(to))||f===activeId){c=0xef4444;em=0xdc2626;op=0.95}else if((upSet.has(f)&&upSet.has(to))||to===activeId){c=0x06b6d4;em=0x0891b2;op=0.95}t.material.color.setHex(c);t.material.emissive.setHex(em);t.material.opacity=op;t.material.needsUpdate=true});
    };
    if(currentSelected) applyHighlights(currentSelected);

    const originalClick=click;
    const enhancedClick=(e)=>{
      originalClick(e);
      // Wait for the raycaster in originalClick to update target / fire onSelect
      setTimeout(() => {
        // Find the new selection by running raycaster again or checking if originalClick fired onSelect
        const rect=renderer.domElement.getBoundingClientRect();pointer.set((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1);ray.setFromCamera(pointer,camera);
        const hits=ray.intersectObjects(nodeMeshes,true);
        if(hits.length && !dragMoved){
           let o=hits[0].object;while(o&&!o.userData.asset)o=o.parent;
           if(o?.userData.asset){
             currentSelected = o.userData.asset.id;
             applyHighlights(currentSelected);
           }
        }
      }, 10);
    };
    renderer.domElement.removeEventListener('click',click);
    renderer.domElement.addEventListener('click',enhancedClick);
    
    return ()=>{alive=false;cancelAnimationFrame(raf);window.removeEventListener('resize',resize);renderer.domElement.removeEventListener('pointerdown',pointerDown);renderer.domElement.removeEventListener('pointermove',pointerMove);renderer.domElement.removeEventListener('pointerup',pointerUp);renderer.domElement.removeEventListener('pointercancel',pointerUp);renderer.domElement.removeEventListener('click',enhancedClick);renderer.domElement.removeEventListener('wheel',wheel);zoomInButtons.forEach(b=>b.removeEventListener('click',zoomIn));zoomOutButtons.forEach(b=>b.removeEventListener('click',zoomOut));resetButtons.forEach(b=>b.removeEventListener('click',resetCamera));scene.traverse(o=>{o.geometry?.dispose?.();if(o.material){if(Array.isArray(o.material))o.material.forEach(m=>m.dispose?.());else o.material.dispose?.()}if(o.material?.map)o.material.map.dispose?.()});renderer.dispose();renderer.domElement.remove()};
  }
  window.KairosObservatory={mount};
})();