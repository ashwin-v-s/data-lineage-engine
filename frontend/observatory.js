/*
 * Kairos 3D lineage garden.
 *
 * The persisted catalog edges drive a layered left-to-right DAG: every column is
 * one lineage hop, cards carry the asset label, and curved arrows run from a
 * dependency into its consumer.  The graph sits in a lit outdoor environment
 * (sky, sun, grass, trees) so it reads as a place rather than a wireframe, but
 * the layout still comes only from the edge list: nothing is positioned by asset
 * id or schema name.
 */
(()=>{
  const T = window.THREE;
  if(!T) return;
  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  const CARD_W=5.6, CARD_H=1.8, PITCH_Y=2.55, LAYER_GAP=2.4, INNER_GAP=1.3, MAX_ROWS=8;
  const KIND_COLOR={source:0x1f9d8b, transform:0x6d5bd0, output:0x2f7de1};
  const KIND_HEX={source:'#128173', transform:'#5b46c4', output:'#1f68c4'};
  const EDGE_BASE=0x2f6b5f;
  const SKY_TOP='#2f6fc4', SKY_MID='#9cc9ef', SKY_LOW='#e4f0d8', GROUND_HAZE='#cfe4bf';

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
    const camera=new T.PerspectiveCamera(42,Math.max(1,host.clientWidth)/Math.max(1,host.clientHeight),.1,600);
    const renderer=new T.WebGLRenderer({antialias:true,alpha:false,powerPreference:'high-performance'});
    renderer.domElement.dataset.kairosScene='true';
    renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,1.75));
    renderer.setSize(host.clientWidth||720,host.clientHeight||490);
    renderer.setClearColor?.(0xcfe4bf,1);
    renderer.outputColorSpace=T.SRGBColorSpace;
    renderer.toneMapping=T.ACESFilmicToneMapping;
    renderer.toneMappingExposure=.98;
    renderer.shadowMap.enabled=true;
    renderer.shadowMap.type=T.PCFSoftShadowMap;
    host.prepend(renderer.domElement);

    /* ---- sky ------------------------------------------------------------- */
    const skyCanvas=document.createElement('canvas'); skyCanvas.width=1024; skyCanvas.height=512;
    const skyCtx=skyCanvas.getContext('2d');
    const skyGrad=skyCtx.createLinearGradient(0,0,0,512);
    skyGrad.addColorStop(0,SKY_TOP); skyGrad.addColorStop(.55,SKY_MID); skyGrad.addColorStop(.82,SKY_LOW); skyGrad.addColorStop(1,GROUND_HAZE);
    skyCtx.fillStyle=skyGrad; skyCtx.fillRect(0,0,1024,512);
    if(skyCtx.createRadialGradient){
      const sunGlow=skyCtx.createRadialGradient(250,96,6,250,96,210);
      sunGlow.addColorStop(0,'rgba(255,253,238,.95)');
      sunGlow.addColorStop(.05,'rgba(255,250,220,.7)');
      sunGlow.addColorStop(.2,'rgba(255,246,200,.26)');
      sunGlow.addColorStop(1,'rgba(255,246,200,0)');
      skyCtx.fillStyle=sunGlow; skyCtx.fillRect(0,0,1024,512);
      /* Thin, soft cloud bands rather than white blocks. */
      [[560,120,300,22],[780,180,360,16],[420,210,220,12]].forEach(c=>{
        const cloud=skyCtx.createRadialGradient(c[0],c[1],2,c[0],c[1],c[2]/2);
        cloud.addColorStop(0,'rgba(255,255,255,.5)');
        cloud.addColorStop(1,'rgba(255,255,255,0)');
        skyCtx.fillStyle=cloud;
        skyCtx.fillRect(c[0]-c[2]/2,c[1]-c[3],c[2],c[3]*2);
      });
    }
    const skyTex=new T.CanvasTexture(skyCanvas); skyTex.colorSpace=T.SRGBColorSpace;
    scene.background=skyTex;
    scene.fog=new T.Fog(0xd7e8c9,90,320);

    let envRT=null,pmrem=null,envTex=null;
    if(T.PMREMGenerator){
      try{
        envTex=new T.CanvasTexture(skyCanvas);
        envTex.colorSpace=T.SRGBColorSpace;
        envTex.mapping=T.EquirectangularReflectionMapping;
        pmrem=new T.PMREMGenerator(renderer);
        envRT=pmrem.fromEquirectangular(envTex);
        scene.environment=envRT.texture;
      }catch(error){ envRT=null; }
    }

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
    const positions={};
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
    const groundY=bounds.minY-3.8;

    /* ---- terrain --------------------------------------------------------- */
    const grassCanvas=document.createElement('canvas'); grassCanvas.width=512; grassCanvas.height=512;
    const grassCtx=grassCanvas.getContext('2d');
    grassCtx.fillStyle='#679a4a'; grassCtx.fillRect(0,0,512,512);
    /* Broad mottled patches read as a lawn; hard stripes read as a board game. */
    if(grassCtx.createRadialGradient){
      const patches=['rgba(97,148,74,.55)','rgba(78,126,58,.45)','rgba(126,171,92,.4)','rgba(70,116,52,.35)'];
      for(let i=0;i<46;i++){
        const cx=(i*173)%512,cy=(i*311)%512,r=28+((i*47)%70);
        const blot=grassCtx.createRadialGradient(cx,cy,2,cx,cy,r);
        blot.addColorStop(0,patches[i%patches.length]);
        blot.addColorStop(1,'rgba(100,150,75,0)');
        grassCtx.fillStyle=blot;
        grassCtx.fillRect(cx-r,cy-r,r*2,r*2);
      }
    }
    const blades=['#568640','#6b9c4e','#4c7c3a','#78a95b','#62934a','#87b367'];
    for(let i=0;i<1800;i++){
      const x=(i*97)%512,y=(i*211)%512;
      grassCtx.fillStyle=blades[i%blades.length];
      grassCtx.fillRect(x,y,2,3+(i%3));
    }
    const grassTex=new T.CanvasTexture(grassCanvas); grassTex.colorSpace=T.SRGBColorSpace;
    const ground=new T.Mesh(
      new T.PlaneGeometry(Math.max(420,contentW*6),Math.max(320,contentH*7)),
      new T.MeshStandardMaterial({map:grassTex,color:0xffffff,roughness:.95,metalness:0})
    );
    ground.rotation.x=-Math.PI/2; ground.position.set(0,groundY,-70); ground.receiveShadow=true;
    scene.add(ground);

    /* Distant hills stay far behind the graph so they read as horizon, not walls. */
    const hillMat=new T.MeshStandardMaterial({color:0x759c60,roughness:1,metalness:0});
    [[-contentW*.8,-165,74,10,52],[contentW*.45,-205,96,14,66],[contentW*1.15,-170,64,9,44]].forEach(h=>{
      const hill=new T.Mesh(new T.SphereGeometry(1,28,20),hillMat);
      hill.scale.set(h[2],h[3],h[4]); hill.position.set(h[0],groundY-1.6,h[1]);
      scene.add(hill);
    });

    /* Vegetation lives outside the graph's silhouette: side rows plus a far
       back row, so nothing ever grows in front of a lineage card. */
    const envRadius=Math.max(46,contentW/2+26);
    const trunkMat=new T.MeshStandardMaterial({color:0x6b4b32,roughness:.9,metalness:0});
    const leafMats=[0x3f7b34,0x4d8f3d,0x356d2c,0x5a9c47].map(c=>new T.MeshStandardMaterial({color:c,roughness:.85,metalness:0}));
    const treeSpots=[];
    const sideOffset=contentW/2+17;
    for(let i=0;i<5;i++){
      const t=i/4;
      treeSpots.push([-(sideOffset+t*24),-12+t*30,1.2+((i*7)%5)/22]);
      treeSpots.push([sideOffset+t*26,-8+t*28,1.25+((i*11)%4)/22]);
    }
    for(let i=0;i<7;i++){
      const t=(i/6)*2-1;
      treeSpots.push([t*(contentW/2+46),-82-((i*13)%20),1.12]);
    }
    treeSpots.forEach((spot,i)=>{
      const x=spot[0],z=spot[1],scale=spot[2];
      const tree=new T.Group(); tree.position.set(x,groundY,z); scene.add(tree);
      const trunk=new T.Mesh(new T.CylinderGeometry(.26*scale,.4*scale,2.9*scale,8),trunkMat);
      trunk.position.y=1.45*scale; trunk.castShadow=true; tree.add(trunk);
      const leaf=leafMats[i%leafMats.length];
      for(let k=0;k<3;k++){
        const canopy=new T.Mesh(new T.SphereGeometry((1.42-(k*.16))*scale,18,14),leaf);
        canopy.position.set((k-1)*.66*scale,(2.95+k*.92)*scale,((k%2)*.44-.22)*scale);
        canopy.castShadow=true; tree.add(canopy);
      }
      tree.rotation.y=i*1.7;
    });
    const shrubMat=new T.MeshStandardMaterial({color:0x4c8a3c,roughness:.9,metalness:0});
    for(let i=0;i<8;i++){
      const side=i%2?1:-1;
      const x=side*(contentW/2+10+((i*29)%9));
      const z=10+(i%4)*7;
      const bush=new T.Mesh(new T.SphereGeometry(.6+((i*17)%5)/12,14,10),shrubMat);
      bush.position.set(x,groundY+.4,z); bush.scale.y=.8; bush.castShadow=true; scene.add(bush);
    }
    const rockMat=new T.MeshStandardMaterial({color:0x9aa193,roughness:.95,metalness:0});
    for(let i=0;i<6;i++){
      const side=i%2?1:-1;
      const rock=new T.Mesh(new T.SphereGeometry(.42+((i*13)%4)/10,10,8),rockMat);
      rock.position.set(side*(contentW/2+8+((i*7)%5)),groundY+.18,14+((i*9)%12));
      rock.scale.y=.6; rock.castShadow=true; scene.add(rock);
    }
    /* Flowering beds at the near corners keep the foreground alive without
       ever stepping in front of a card. */
    const bloomMats=[0xe9a7c3,0xf2dea0,0xc9c6f2,0xf4f0e6].map(c=>new T.MeshStandardMaterial({color:c,roughness:.75,metalness:0}));
    for(let i=0;i<12;i++){
      const side=i%2?1:-1;
      const bloom=new T.Mesh(new T.SphereGeometry(.4+((i*11)%5)/14,12,9),bloomMats[i%bloomMats.length]);
      bloom.position.set(side*(contentW*.18+((i*13)%9)*contentW*.045),groundY+.26,17+((i*7)%8)*2.4);
      bloom.scale.y=.62; bloom.castShadow=true; scene.add(bloom);
    }
    /* A low hedge line behind the graph gives the clearing a back edge. */
    const hedgeMat=new T.MeshStandardMaterial({color:0x3f7434,roughness:.92,metalness:0});
    for(let i=0;i<11;i++){
      const x=(i/10-.5)*(contentW+44);
      const hedge=new T.Mesh(new T.SphereGeometry(1.7,14,10),hedgeMat);
      hedge.position.set(x,groundY+1.15,-30-((i*5)%7));
      hedge.scale.set(1.35,.82,1.1); hedge.castShadow=true; scene.add(hedge);
    }

    /* ---- sunlight -------------------------------------------------------- */
    scene.add(new T.HemisphereLight(0xcfe6ff,0x50743a,1.2));
    const sun=new T.DirectionalLight(0xfff4e0,2.5);
    sun.position.set(-envRadius*.55,groundY+88,46);
    sun.castShadow=true;
    const shadowSize=(window.innerWidth||1600)<900?1024:2048;
    sun.shadow.mapSize.set(shadowSize,shadowSize);
    sun.shadow.camera.left=-(contentW/2+22); sun.shadow.camera.right=contentW/2+22;
    sun.shadow.camera.top=contentH/2+26; sun.shadow.camera.bottom=-(contentH/2+26);
    sun.shadow.camera.near=20; sun.shadow.camera.far=260; sun.shadow.bias=-0.0006;
    if(sun.shadow.radius!==undefined) sun.shadow.radius=3;
    scene.add(sun);
    if(sun.target){
      sun.target.position.set(0,(bounds.minY+bounds.maxY)/2,0);
      scene.add(sun.target);
    }
    const fill=new T.PointLight(0xfff6e0,.5,120,2); fill.position.set(-10,groundY+12,22); scene.add(fill);

    const root=new T.Group(); scene.add(root);
    const dataLayer=new T.Group(); root.add(dataLayer);
    const nodeMeshes=[];
    const edgeMeshes=[];
    const pickables=[];
    const animated=[];
    const floaters=[];

    /* ---- labels and plaques ---------------------------------------------- */
    function makeLabel(asset){
      const canvas=document.createElement('canvas'); canvas.width=512; canvas.height=168;
      const ctx=canvas.getContext('2d');
      const accent=KIND_HEX[asset.kind]||'#5b46c4';
      ctx.fillStyle='rgba(250,247,238,.97)'; ctx.fillRect(2,2,508,164);
      ctx.strokeStyle=accent; ctx.lineWidth=5; ctx.strokeRect(3,3,506,162);
      ctx.fillStyle=accent; ctx.fillRect(3,3,14,162);
      ctx.fillStyle='#15211b'; ctx.font='700 44px "Segoe UI",Arial,sans-serif';
      const name=String(asset.name||asset.path||'asset');
      ctx.fillText(name.length>24?name.slice(0,23)+'…':name,36,70);
      ctx.fillStyle='#4c6257'; ctx.font='26px "Segoe UI",Arial,sans-serif';
      const sub=String(asset.schema||'default')+'  ·  '+String(asset.kind||'asset');
      ctx.fillText(sub.length>44?sub.slice(0,43)+'…':sub,36,114);
      ctx.fillStyle=accent; ctx.font='700 21px "Segoe UI",Arial,sans-serif';
      ctx.fillText(String(asset.kind||'asset').toUpperCase(),36,148);
      const tex=new T.CanvasTexture(canvas); tex.colorSpace=T.SRGBColorSpace;
      const sprite=new T.Sprite(new T.SpriteMaterial({map:tex,transparent:true,depthWrite:false}));
      sprite.scale.set(CARD_W*.96,CARD_W*.96*(168/512),1);
      return sprite;
    }

    function makeBandLabel(text){
      const canvas=document.createElement('canvas'); canvas.width=256; canvas.height=64;
      const ctx=canvas.getContext('2d');
      ctx.fillStyle='rgba(27,58,38,.82)'; ctx.fillRect(0,0,256,64);
      ctx.fillStyle='#f3f8ee'; ctx.font='700 28px "Segoe UI",Arial,sans-serif';
      ctx.textAlign='center'; ctx.fillText(text,128,42);
      const tex=new T.CanvasTexture(canvas); tex.colorSpace=T.SRGBColorSpace;
      const sprite=new T.Sprite(new T.SpriteMaterial({map:tex,transparent:true,depthWrite:false}));
      sprite.scale.set(4.4,1.1,1);
      return sprite;
    }

    bands.forEach((band,index)=>{
      const bandHeight=Math.max(2.4,band.rows*PITCH_Y+1.1);
      const glass=new T.Mesh(
        new T.PlaneGeometry(band.width+1.1,bandHeight),
        new T.MeshPhysicalMaterial({color:0xeaf6e4,transparent:true,opacity:.16,roughness:.05,metalness:0,clearcoat:1,clearcoatRoughness:.05,depthWrite:false,side:T.DoubleSide})
      );
      glass.position.set(band.x0+band.width/2,(bounds.minY+bounds.maxY)/2,-.6);
      glass.material.opacity=.1;
      dataLayer.add(glass);
      const caption=makeBandLabel(index===0?'ROOTS':'HOP '+index);
      caption.position.set(band.x0+band.width/2,(bounds.minY+bounds.maxY)/2+bandHeight/2+.8,.1);
      dataLayer.add(caption);
    });

    list.forEach((a,i)=>{
      const pos=positions[a.id];
      const group=new T.Group(); group.position.copy(pos); group.userData.asset=a; dataLayer.add(group);
      const color=KIND_COLOR[a.kind]||KIND_COLOR.transform;
      const isSelected=a.id===selected;
      const bodyMat=new T.MeshPhysicalMaterial({color:0xf7f2e6,roughness:.5,metalness:.04,clearcoat:.4,clearcoatRoughness:.35,transparent:true,opacity:1});
      const body=new T.Mesh(new T.BoxGeometry(CARD_W,CARD_H,.26),bodyMat);
      body.userData.asset=a; body.castShadow=true; body.receiveShadow=true; body.renderOrder=1; group.add(body); pickables.push(body);
      const strip=new T.Mesh(new T.BoxGeometry(.2,CARD_H,.3),new T.MeshStandardMaterial({color,roughness:.45,metalness:.1,transparent:true,opacity:1}));
      strip.position.set(-CARD_W/2+.1,0,.02); strip.castShadow=true; group.add(strip);
      const halo=new T.Mesh(
        new T.TorusGeometry(1,.045,10,72),
        new T.MeshBasicMaterial({color:isSelected?0xffffff:0x5b7f9c,transparent:true,opacity:isSelected?.98:.3})
      );
      halo.scale.set(CARD_W/2+.16,CARD_H/2+.16,1); halo.position.z=-.22;
      halo.visible=isSelected; group.add(halo);
      const label=makeLabel(a); label.position.z=.2; label.renderOrder=4; group.add(label);
      /* The plaque is a physical object, so it needs a second face: without it
         the names vanish as soon as the viewer orbits behind the graph. */
      const backLabel=new T.Sprite(new T.SpriteMaterial({map:label.material.map,transparent:true,depthWrite:false}));
      backLabel.scale.set(label.scale.x,label.scale.y,1);
      backLabel.position.z=-.34; backLabel.renderOrder=4;
      group.add(backLabel);

      const orb=new T.Mesh(
        new T.SphereGeometry(.44,24,18),
        new T.MeshPhysicalMaterial({color,roughness:.12,metalness:.16,clearcoat:1,clearcoatRoughness:.06,emissive:color,emissiveIntensity:.24,transparent:true,opacity:1})
      );
      orb.position.set(CARD_W/2-.62,CARD_H/2+.68,.22); orb.castShadow=true; group.add(orb);
      const orbit=new T.Mesh(new T.TorusGeometry(.57,.015,8,48),new T.MeshBasicMaterial({color,transparent:true,opacity:.4}));
      orbit.position.copy(orb.position); orbit.rotation.x=1.1; orbit.rotation.y=.45; group.add(orbit);
      floaters.push({orb,orbit,baseY:orb.position.y,phase:i*1.37});

      nodeMeshes.push({id:a.id,group,body,label,backLabel,halo,orb,orbit,strip});
    });

    /* ---- edges with directional arrowheads ------------------------------- */
    visEdges.forEach(e=>{
      const from=positions[e[0]],to=positions[e[1]];
      if(!from||!to) return;
      const start=new T.Vector3(from.x+CARD_W/2,from.y,.05);
      const end=new T.Vector3(to.x-CARD_W/2-.3,to.y,.05);
      const dx=end.x-start.x;
      const c1=new T.Vector3(start.x+dx*.45,start.y,0);
      const c2=new T.Vector3(end.x-dx*.45,end.y,0);
      const curve=new T.CubicBezierCurve3(start,c1,c2,end);
      const mat=new T.MeshStandardMaterial({color:EDGE_BASE,roughness:.42,metalness:.28,emissive:0x173b34,emissiveIntensity:.5,transparent:true,opacity:.92});
      const tube=new T.Mesh(new T.TubeGeometry(curve,26,.07,8,false),mat);
      tube.userData={from:e[0],to:e[1]}; tube.castShadow=true; dataLayer.add(tube);
      const theta=Math.atan2(end.y-c2.y,end.x-c2.x);
      const arrow=new T.Mesh(new T.ConeGeometry(.24,.7,10),mat);
      arrow.position.set(end.x-Math.cos(theta)*.2,end.y-Math.sin(theta)*.2,.05);
      arrow.rotation.z=theta-Math.PI/2; arrow.castShadow=true; dataLayer.add(arrow);
      const bead=new T.Mesh(new T.SphereGeometry(.14,10,8),new T.MeshBasicMaterial({color:0xffffff}));
      dataLayer.add(bead);
      animated.push({bead,curve,phase:Math.random()});
      edgeMeshes.push({tube,arrow,mat,from:e[0],to:e[1]});
    });

    /* ---- camera ---------------------------------------------------------- */
    const center=new T.Vector3(0,(bounds.minY+bounds.maxY)/2,0);
    let baseRadius=24;
    /* The canvas can mount before the panel has its final CSS size, so measure
       the live box rather than trusting the size captured at mount time. */
    const measure=()=>{
      const rect=host.getBoundingClientRect?.();
      return {
        w:Math.max(1,Math.round(rect?.width||host.clientWidth||renderer.domElement.clientWidth||720)),
        h:Math.max(1,Math.round(rect?.height||host.clientHeight||renderer.domElement.clientHeight||490)),
      };
    };
    const computeFit=()=>{
      const {w,h}=measure();
      const aspect=Math.max(.2,w/h);
      camera.aspect=aspect;
      camera.updateProjectionMatrix();
      const vFov=42*Math.PI/180;
      const byHeight=contentH/(2*Math.tan(vFov/2));
      const byWidth=contentW/(2*Math.tan(vFov/2)*aspect);
      baseRadius=Math.max(byHeight,byWidth)*1.06;
    };
    computeFit();
    const target=new T.Vector3(center.x,center.y,center.z);
    if(selected&&positions[selected]) target.copy(positions[selected]);
    let rotY=0,rotX=.09,zoom=1;
    const WALK_LIMIT=Math.max(80,envRadius*1.6);
    const PITCH_MIN=-.3,PITCH_MAX=1.2;
    const updateCamera=()=>{
      target.x=clamp(target.x,-WALK_LIMIT,WALK_LIMIT);
      target.z=clamp(target.z,-WALK_LIMIT,WALK_LIMIT);
      target.y=clamp(target.y,groundY+1.4,groundY+contentH+40);
      const r=baseRadius/zoom;
      camera.position.set(
        target.x+Math.sin(rotY)*Math.cos(rotX)*r,
        target.y+Math.sin(rotX)*r,
        target.z+Math.cos(rotY)*Math.cos(rotX)*r
      );
      /* Never let a free orbit or walk drop the viewer under the lawn. */
      if(camera.position.y<groundY+1.6) camera.position.y=groundY+1.6;
      camera.lookAt(target);
    };
    updateCamera();

    /* ---- interaction ----------------------------------------------------- */
    const ray=new T.Raycaster(),pointer=new T.Vector2();
    let down=false,panMode=false,lastX=0,lastY=0,downX=0,downY=0,dragMoved=false,suppressClick=false;
    renderer.domElement.tabIndex=0;
    renderer.domElement.style.outline='none';
    renderer.domElement.style.touchAction='none';
    const pointerDown=e=>{
      down=true;dragMoved=false;suppressClick=false;
      panMode=e.button===2||e.button===1||e.shiftKey;
      lastX=e.clientX;lastY=e.clientY;downX=e.clientX;downY=e.clientY;
      renderer.domElement.focus?.();
      renderer.domElement.style.cursor=panMode?'move':'grabbing';
      renderer.domElement.setPointerCapture?.(e.pointerId);
    };
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
        if(hovered){
          hovered.group.scale.setScalar(1);
          hovered.group.position.y=positions[hovered.id].y;
        }
        hovered=next;
        if(hovered){
          hovered.group.scale.setScalar(1.03);
          hovered.group.position.y=positions[hovered.id].y+.14;
        }
      }
      renderer.domElement.style.cursor=hovered?'pointer':'grab';
    };
    const pointerMove=e=>{
      if(!down){hoverX=e.clientX;hoverY=e.clientY;hoverDirty=true;return}
      const dx=e.clientX-lastX,dy=e.clientY-lastY;
      if(Math.abs(e.clientX-downX)+Math.abs(e.clientY-downY)>3) dragMoved=true;
      if(panMode){
        const scale=(baseRadius/zoom)*.0018;
        target.x-=Math.cos(rotY)*dx*scale;
        target.z+=Math.sin(rotY)*dx*scale;
        target.y+=dy*scale;
      }else{
        /* Unclamped yaw: a full 360° turn around the graph. */
        rotY-=dx*.005;
        rotX=clamp(rotX+dy*.003,PITCH_MIN,PITCH_MAX);
      }
      lastX=e.clientX;lastY=e.clientY;
      updateCamera();
    };
    const pointerUp=()=>{
      if(!down)return;
      down=false;panMode=false;suppressClick=dragMoved;dragMoved=false;
      renderer.domElement.style.cursor=hovered?'pointer':'grab';
    };
    const contextMenu=e=>e.preventDefault();
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
        const dim=onPath?1:.28;
        node.body.material.opacity=dim;
        node.label.material.opacity=dim;
        node.backLabel.material.opacity=dim;
        node.strip.material.opacity=dim;
        node.orb.material.opacity=dim;
        node.orbit.material.opacity=onPath?.45:.12;
        node.body.material.emissiveIntensity=node.id===activeId?.22:onPath?.1:0;
        node.orb.material.emissiveIntensity=node.id===activeId?.5:onPath?.3:.1;
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
        let color=EDGE_BASE,emissive=0x173b34,opacity=downstream||upstream?.95:.2;
        if(downstream||edge.from===activeId){color=0xe0483e;emissive=0x8f1d17;opacity=.95}
        else if(upstream||edge.to===activeId){color=0x1d6fe8;emissive=0x134b9c;opacity=.95}
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
    const resetCamera=()=>{target.copy(center);rotY=0;rotX=.09;zoom=1;updateCamera()};

    /* ---------- free movement: walk the garden with keys or pan-drag --------- */
    const keys=new Set();
    let hostHovered=false;
    const MOVEMENT_KEYS=['w','a','s','d','q','e','arrowleft','arrowright','arrowup','arrowdown'];
    const keyAllowed=()=>hostHovered||document.activeElement===renderer.domElement;
    const keydown=e=>{
      const tag=(e.target&&e.target.tagName)||'';
      if(/^(INPUT|TEXTAREA|SELECT)$/.test(tag)||e.target?.isContentEditable) return;
      if(!keyAllowed()) return;
      const key=String(e.key||'').toLowerCase();
      if(!MOVEMENT_KEYS.includes(key)) return;
      keys.add(key); e.preventDefault();
    };
    const keyup=e=>{keys.delete(String(e.key||'').toLowerCase())};
    const clearKeys=()=>keys.clear();
    const pointerEnter=()=>{hostHovered=true};
    const pointerLeave=()=>{hostHovered=false};
    window.addEventListener('keydown',keydown);
    window.addEventListener('keyup',keyup);
    window.addEventListener('blur',clearKeys);
    renderer.domElement.addEventListener('pointerenter',pointerEnter);
    renderer.domElement.addEventListener('pointerleave',pointerLeave);
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
    renderer.domElement.addEventListener('contextmenu',contextMenu);
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
      /* Movement is input, not decoration: it runs even for reduced motion. */
      if(keys.size){
        let forward=0,strafe=0,rise=0;
        if(keys.has('w')) forward+=1;
        if(keys.has('s')) forward-=1;
        if(keys.has('d')) strafe+=1;
        if(keys.has('a')) strafe-=1;
        if(keys.has('e')) rise+=1;
        if(keys.has('q')) rise-=1;
        if(keys.has('arrowleft')) rotY+=1.7*delta;
        if(keys.has('arrowright')) rotY-=1.7*delta;
        if(keys.has('arrowup')) rotX=clamp(rotX+.75*delta,PITCH_MIN,PITCH_MAX);
        if(keys.has('arrowdown')) rotX=clamp(rotX-.75*delta,PITCH_MIN,PITCH_MAX);
        const speed=Math.max(8,baseRadius/zoom*.5)*delta;
        const fx=-Math.sin(rotY),fz=-Math.cos(rotY);
        const rx=Math.cos(rotY),rz=-Math.sin(rotY);
        target.x+=(fx*forward+rx*strafe)*speed;
        target.z+=(fz*forward+rz*strafe)*speed;
        target.y+=rise*speed;
        updateCamera();
      }
      if(!motionReduced()){
        elapsed+=delta;
        const t=elapsed*.07;
        animated.forEach(p=>{
          const u=(t+p.phase)%1;
          if(!Number.isFinite(u)) return;
          p.bead.position.copy(p.curve.getPoint(u,beadPoint));
        });
        floaters.forEach(f=>{
          f.orb.position.y=f.baseY+Math.sin(elapsed*.9+f.phase)*.1;
          f.orb.rotation.y+=delta*.5;
          f.orbit.rotation.z+=delta*.35;
        });
      }
      /* Show the face that looks at the viewer, so a full orbit never lands on
         a blank plaque. */
      const frontFace=camera.position.z>=0;
      nodeMeshes.forEach(node=>{ node.label.visible=frontFace; node.backLabel.visible=!frontFace; });
      renderer.render(scene,camera);
    };
    raf=requestAnimationFrame(animate);

    const resize=()=>{
      if(!host.isConnected) return;
      const {w,h}=measure();
      renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,1.75));
      renderer.setSize(w,h);
      computeFit();
      updateCamera();
    };
    window.addEventListener('resize',resize);
    /* One deferred settle covers late layout, then the observer covers resizes
       that never reach window (split panes, sidebar toggles). */
    requestAnimationFrame(()=>{if(alive) resize()});
    let sizeObserver=null;
    if(typeof ResizeObserver!=='undefined'){
      sizeObserver=new ResizeObserver(()=>resize());
      sizeObserver.observe(host);
    }

    const sceneNodes=document.querySelector('#sceneNodes'),sceneEdgeCount=document.querySelector('#sceneEdges');
    if(sceneNodes) sceneNodes.textContent=list.length;
    if(sceneEdgeCount) sceneEdgeCount.textContent=visEdges.filter(e=>positions[e[0]]&&positions[e[1]]).length;
    const captionTitle=host.querySelector('.observatory-caption strong');
    if(captionTitle) captionTitle.textContent='Lineage Garden';
    const captionBody=host.querySelector('.observatory-caption p');
    if(captionBody) captionBody.textContent='Sunlit left-to-right lineage: dependencies on the left, consumers on the right. Drag for a full 360° orbit, right-drag or shift-drag to pan, WASD to walk, Q/E to rise and fall, scroll to zoom. Click an asset to trace its upstream and downstream paths.';
    renderer.domElement.style.cursor='grab';

    if(selected) applyHighlights(selected);

    return ()=>{
      alive=false;
      cancelAnimationFrame(raf);
      window.removeEventListener('resize',resize);
      sizeObserver?.disconnect?.();
      window.removeEventListener('keydown',keydown);
      window.removeEventListener('keyup',keyup);
      window.removeEventListener('blur',clearKeys);
      renderer.domElement.removeEventListener('pointerenter',pointerEnter);
      renderer.domElement.removeEventListener('pointerleave',pointerLeave);
      renderer.domElement.removeEventListener('contextmenu',contextMenu);
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
      envRT?.dispose?.();
      pmrem?.dispose?.();
      envTex?.dispose?.();
      skyTex.dispose?.();
      grassTex.dispose?.();
      renderer.dispose();
      /* dispose() leaves the WebGL context alive; remounting repeatedly would
         exhaust the browser's context limit and blank the view. */
      renderer.forceContextLoss?.();
      renderer.domElement.remove();
    };
  }

  window.KairosObservatory={mount};
})();
