/******/ (function(modules) { // webpackBootstrap
/******/ 	// The module cache
/******/ 	var installedModules = {};
/******/
/******/ 	// The require function
/******/ 	function __webpack_require__(moduleId) {
/******/
/******/ 		// Check if module is in cache
/******/ 		if(installedModules[moduleId])
/******/ 			return installedModules[moduleId].exports;
/******/
/******/ 		// Create a new module (and put it into the cache)
/******/ 		var module = installedModules[moduleId] = {
/******/ 			exports: {},
/******/ 			id: moduleId,
/******/ 			loaded: false
/******/ 		};
/******/
/******/ 		// Execute the module function
/******/ 		modules[moduleId].call(module.exports, module, module.exports, __webpack_require__);
/******/
/******/ 		// Flag the module as loaded
/******/ 		module.loaded = true;
/******/
/******/ 		// Return the exports of the module
/******/ 		return module.exports;
/******/ 	}
/******/
/******/
/******/ 	// expose the modules object (__webpack_modules__)
/******/ 	__webpack_require__.m = modules;
/******/
/******/ 	// expose the module cache
/******/ 	__webpack_require__.c = installedModules;
/******/
/******/ 	// __webpack_public_path__
/******/ 	__webpack_require__.p = "/";
/******/
/******/ 	// Load entry module and return exports
/******/ 	return __webpack_require__(0);
/******/ })
/************************************************************************/
/******/ ({

/***/ 0:
/***/ function(module, exports, __webpack_require__) {

	module.exports = __webpack_require__(1832);


/***/ },

/***/ 1832:
/***/ function(module, exports) {

	(()=>{var M=Object.defineProperty;var N=Object.getOwnPropertySymbols;var q=Object.prototype.hasOwnProperty,z=Object.prototype.propertyIsEnumerable;var A=(n,t,e)=>t in n?M(n,t,{enumerable:!0,configurable:!0,writable:!0,value:e}):n[t]=e,v=(n,t)=>{for(var e in t||(t={}))q.call(t,e)&&A(n,e,t[e]);if(N)for(var e of N(t))z.call(t,e)&&A(n,e,t[e]);return n};var F=(n,t,e)=>new Promise((r,o)=>{var s=i=>{try{c(e.next(i))}catch(u){o(u)}},l=i=>{try{c(e.throw(i))}catch(u){o(u)}},c=i=>i.done?r(i.value):Promise.resolve(i.value).then(s,l);c((e=e.apply(n,t)).next())});var U=function(){var t=arguments.length>0&&arguments[0]!==void 0?arguments[0]:{},e=t.wnd,r=e===void 0?window:e;(function(o,s,l,c,i,u,a,m){if(l in o){o.console&&o.console.log&&o.console.log('FullStory namespace conflict. Please set window["_fs_namespace"].');return}a=o[l]=function(p,d,w){a.q?a.q.push([p,d,w]):a._api(p,d,w)},a.q=[],u=s.createElement(c),u.async=1,u.crossOrigin="anonymous",u.src="https://"+_fs_script,m=s.getElementsByTagName(c)[0],m.parentNode.insertBefore(u,m),a.identify=function(p,d,w){a(i,{uid:p},w),d&&a(i,d,w)},a.setUserVars=function(p,d){a(i,p,d)},a.event=function(p,d,w){a("event",{n:p,p:d},w)},a.anonymize=function(){a.identify(!1)},a.shutdown=function(){a("rec",!1)},a.restart=function(){a("rec",!0)},a.log=function(p,d){a("log",[p,d])},a.consent=function(p){a("consent",!arguments.length||p)},a.identifyAccount=function(p,d){u="account",d=d||{},d.acctId=p,a(u,d)},a.clearUserCookie=function(){},a.setVars=function(p,d){a("setVars",[p,d])},a._w={},m="XMLHttpRequest",a._w[m]=o[m],m="fetch",a._w[m]=o[m],o[m]&&(o[m]=function(){return a._w[m].apply(this,arguments)}),a._v="1.3.0"})(r,r.document,r._fs_namespace,"script","user")},$=function(t){return t==="window"?"document":"".concat(t,".document")},B=function(){var t=arguments.length>0&&arguments[0]!==void 0?arguments[0]:{},e=t.shouldInsertScript,r=e===void 0?!0:e,o=t.globalVar,s=o===void 0?"window":o,l=t.apiVersion,c=l===void 0?"1.3.0":l;return`(function(m,n,e,t,l,o,g,y){
	    if (e in m) {if(m.console && m.console.log) { m.console.log('FullStory namespace conflict. Please set window["_fs_namespace"].');} return;}
	    g=m[e]=function(a,b,s){g.q?g.q.push([a,b,s]):g._api(a,b,s);};g.q=[];`.concat(r?`
	    o=n.createElement(t);o.async=1;o.crossOrigin='anonymous';o.src='https://'+_fs_script;
	    y=n.getElementsByTagName(t)[0];y.parentNode.insertBefore(o,y);`:"",`
	    g.identify=function(i,v,s){g(l,{uid:i},s);if(v)g(l,v,s)};g.setUserVars=function(v,s){g(l,v,s)};g.event=function(i,v,s){g('event',{n:i,p:v},s)};
	    g.anonymize=function(){g.identify(!!0)};
	    g.shutdown=function(){g("rec",!1)};g.restart=function(){g("rec",!0)};
	    g.log = function(a,b){g("log",[a,b])};
	    g.consent=function(a){g("consent",!arguments.length||a)};
	    g.identifyAccount=function(i,v){o='account';v=v||{};v.acctId=i;g(o,v)};
	    g.clearUserCookie=function(){};
	    g.setVars=function(n, p){g('setVars',[n,p]);};
	    g._w={};y='XMLHttpRequest';g._w[y]=m[y];y='fetch';g._w[y]=m[y];
	    if(m[y])m[y]=function(){return g._w[y].apply(this,arguments)};
	    g._v="`).concat(c,`";
	})(`).concat(s,",").concat($(s),",").concat(s,"['_fs_namespace'],'script','user');")},P=function(t){var e=t.orgId,r=t.namespace,o=r===void 0?"FS":r,s=t.debug,l=s===void 0?!1:s,c=t.host,i=c===void 0?"fullstory.com":c,u=t.script,a=u===void 0?"edge.fullstory.com/s/fs.js":u;if(!e)throw new Error("FullStory orgId is a required parameter");window._fs_debug=l,window._fs_host=i,window._fs_script=a,window._fs_org=e,window._fs_namespace=o,U()},he=B();function C(n,t){var e=Object.keys(n);if(Object.getOwnPropertySymbols){var r=Object.getOwnPropertySymbols(n);t&&(r=r.filter(function(o){return Object.getOwnPropertyDescriptor(n,o).enumerable})),e.push.apply(e,r)}return e}function K(n){for(var t=1;t<arguments.length;t++){var e=arguments[t]!=null?arguments[t]:{};t%2?C(Object(e),!0).forEach(function(r){H(n,r,e[r])}):Object.getOwnPropertyDescriptors?Object.defineProperties(n,Object.getOwnPropertyDescriptors(e)):C(Object(e)).forEach(function(r){Object.defineProperty(n,r,Object.getOwnPropertyDescriptor(e,r))})}return n}function H(n,t,e){return t in n?Object.defineProperty(n,t,{value:e,enumerable:!0,configurable:!0,writable:!0}):n[t]=e,n}var g=function(){return window[window._fs_namespace]},J=function(){var t=!!g();if(!t)throw Error("FullStory is not loaded, please ensure the init function is invoked before calling FullStory API functions")},X=function(){J();for(var t=arguments.length,e=new Array(t),r=0;r<t;r++)e[r]=arguments[r];return e.every(function(o){return g()[o]})},y=function(t){return function(){if(window._fs_dev_mode){var e="FullStory is in dev mode and is not recording: ".concat(t," method not executed");return console.warn(e),e}if(X(t)){var r;return(r=g())[t].apply(r,arguments)}return console.warn("FS.".concat(t," not ready")),null}},x=y("event"),be=y("log"),Ee=y("getCurrentSessionURL"),W=y("identify"),Ie=y("setUserVars"),Oe=y("consent"),Q=y("shutdown"),ke=y("restart"),Ne=y("anonymize"),Ae=y("setVars"),Y=function(t,e){var r=K({},t);if(g()){console.warn("The FullStory snippet has already been defined elsewhere (likely in the <head> element)");return}if(r.recordCrossDomainIFrames&&(window._fs_run_in_iframe=!0),r.recordOnlyThisIFrame&&(window._fs_is_outer_script=!0),r.cookieDomain&&(window._fs_cookie_domain=r.cookieDomain),r.debug===!0&&(r.script?console.warn("Ignoring `debug = true` because `script` is set"):r.script="edge.fullstory.com/s/fs-debug.js"),P(r),e&&g()("observe",{type:"start",callback:e}),r.devMode===!0){var o="FullStory was initialized in devMode and will stop recording";x("FullStory Dev Mode",{message_str:o}),Q(),window._fs_dev_mode=!0,console.warn(o)}},Z=function(t,e){return function(){if(window._fs_initialized){e&&console.warn(e);return}t.apply(void 0,arguments),window._fs_initialized=!0}},ee=Z(Y,"FullStory init has already been called once, additional invocations are ignored");var ne=()=>new Array(5).fill(0).map(()=>Math.random().toString(36).slice(-1)).join(""),_=()=>Date.now().toString()+"-"+ne(),re=n=>n.toLowerCase().replace(/[^a-z0-9\.]+/g,"_"),T=(n,t)=>{let e=[n.category,n.action,n.label].filter(s=>s!=null),r=e.join(".").replace(/-/g,"_"),o=e.map(re).join(".");return t&&r!=o&&console.warn(`frontend-tracking: topic was normalized from '${r}' to '${o}'`),o};var S=()=>{let n=navigator.language||navigator.userLanguage;return typeof n=="string"?n.substr(0,2).toLowerCase():null},b=["localhost","stable-staging.com","jimdosite-stage.com","jimdo-platform.net","stage.jimdo.systems","jimdo-dev-staging.com","storybook","pv-url"];var oe=()=>navigator.sendBeacon.bind(navigator),E=(n,t,e)=>{let r=e!=null?e:oe();try{r(n,t)}catch(o){ae(n,t)}},ae=(n,t)=>F(void 0,null,function*(){yield fetch(n,{method:"POST",body:t,headers:{"Content-Type":"application/json"},mode:"no-cors",credentials:"omit",cache:"no-cache",referrerPolicy:"origin",keepalive:!0})});var se=!1;typeof window!="undefined"&&(window._fs_ready=function(){se=!0});var Ge=_();var ie="https://at.stage.jimdo.systems/anon",ce="https://at.prod.jimdo.systems/anon";var de=_(),ue=_(),j=n=>{let t=0;return e=>r=>{var u,a,m,p,d,w,k;let o=T(r,e.logToConsole||!1),s=(a=(u=e==null?void 0:e.getSeedPayload)==null?void 0:u.call(e))!=null?a:{},l=v(v({language:(p=(m=e==null?void 0:e.getLanguage)==null?void 0:m.call(e))!=null?p:S(),location:(w=(d=e==null?void 0:e.getLocation)==null?void 0:d.call(e))!=null?w:document.location.href},s),r.payload),c={meta:JSON.stringify(l),topic:o,seq:t++,sid:n,websiteId:(k=e==null?void 0:e.websiteId)==null?void 0:k.call(e)};e.logToConsole&&console.log(`frontend-tracking: anonymous event "${c.topic}" tracked`,l,c);let i=JSON.stringify(c);E(e.endpoint,i,e==null?void 0:e.sendBeacon)}},h=j(de),le=j(ue);function I(n){return b.some(t=>n.includes(t))?ie:ce}var L=(n,t)=>n instanceof HTMLElement&&n.dataset&&n.dataset[t]?n:n.parentNode?L(n.parentNode,t):null,pe=(n,t,e,r,o)=>{var c;let s={},l=(c=e.dataset[r])!=null?c:"";return(o||[]).forEach(i=>{var u;s[i]=(u=e.attributes.getNamedItem(i))==null?void 0:u.value}),Object.keys(e.dataset).filter(i=>i.indexOf("track-")===0).forEach(i=>{s[i.replace("track-","")]=e.dataset[i]}),{category:n,action:t,label:l,payload:s}},D=(n,t,e,r,o)=>s=>{let{target:l}=s;if(l instanceof Node){let c=L(l,e);if(c instanceof HTMLElement){let i=pe(n,t,c,e,r);o(i)}}},R=!1,f={};function me(){if(typeof performance!="undefined"&&typeof performance.getEntriesByType=="function"){let n=performance.getEntriesByType("navigation");if(n.length>0){let t=n[0];f.domInteractive=Math.round(t.domInteractive),f.domComplete=Math.round(t.domComplete)}}}function fe(){if(!(R||typeof PerformanceObserver=="undefined")){try{new PerformanceObserver(n=>{for(let t of n.getEntriesByName("first-contentful-paint"))f.fcp=Math.round(t.startTime)}).observe({type:"paint",buffered:!0}),new PerformanceObserver(n=>{let t=n.getEntries().pop();t&&(f.lcp=Math.round(t.renderTime||t.startTime))}).observe({type:"largest-contentful-paint",buffered:!0}),new PerformanceObserver(n=>{let t=n.getEntries()[0];t&&(f.fid=Math.round(t.processingStart-t.startTime))}).observe({type:"first-input",buffered:!0}),new PerformanceObserver(n=>{let t=n.getEntries().map(e=>e.value);t.length&&(f.cls=Math.round(t.reduce((e,r)=>e+r)*1e3)/1e3)}).observe({type:"layout-shift",buffered:!0})}catch(n){return}R=!0}}function V(){return fe(),me(),{domInteractive:f.domInteractive,domComplete:f.domComplete,fcp:f.fcp,lcp:f.lcp,fid:f.fid,cls:f.cls}}V();var we=n=>{let t={};return n?n.substr(1).split("&").reduce((e,r)=>{let[o,s]=r.split("=");return e[o]=s?decodeURIComponent(s.replace(/\+/g," ")):"",e},t):t},O=(n,t)=>{if(typeof document=="undefined"||typeof window=="undefined")return;let e=Date.now(),r=0,o=(s,l)=>{let c=we(window.location.search);t({category:n,action:"page",label:s,payload:{timeSpentOnPageInMS:Date.now()-e,performance:l?V():void 0,scrollDepth:window.scrollY,referrer:document.referrer,maxScrollDepth:r,query:c,auto:!0}})};document.readyState==="complete"?o("complete",!1):document.readyState==="loading"&&o("loading",!1),document.addEventListener("readystatechange",()=>{document.readyState==="interactive"?o("interactive",!1):document.readyState==="complete"&&o("complete",!1)}),document.addEventListener("visibilitychange",()=>{document.visibilityState==="visible"?o("visible",!1):document.visibilityState==="hidden"&&o("hidden",!0)}),window.addEventListener("beforeunload",()=>{o("unload",!0)}),document.body.addEventListener("click",D(n,"click","tracking",["href","text"],t)),document.querySelectorAll("[data-tracking-onhover]").forEach(s=>{s.addEventListener("mouseenter",D(n,"mouseenter","tracking",["href","text"],t))})};var G=I(window.location.host);(window.location.host.indexOf("jimdo.dev")!==-1||window.location.host.indexOf("jimdofree.dev")!==-1)&&(G="https://at.stage.jimdo.systems/anon");var ge=h({endpoint:G,logToConsole:!1,websiteId:function(){return window.jimdoData.websiteId}});window.AnonTracking=h;window.track_anon=ge;window.addAutomatedTracking=O;})();


/***/ }

/******/ });
//# sourceMappingURL=sourcemaps/at.js.f4680ead6f240367d9f9.js.map