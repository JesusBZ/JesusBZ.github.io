if(!Array.prototype.indexOf){Array.prototype.indexOf=function(elt){var len=this.length>>>0;var from=Number(arguments[1])||0;from=(from<0)?Math.ceil(from):Math.floor(from);if(from<0)
from+=len;for(;from<len;from++){if(from in this&&this[from]===elt)
return from;}
return-1;};}
HTMLWidgets.widget({name:"dygraphs",type:"output",factory:function(el,width,height){var dygraph=null;var groups=this.groups;if(window.navigator.userAgent.indexOf(" Qt/")>0)
el.className+=" qt";return{renderValue:function(x){var thiz=this;var attrs=x.attrs;attrs.file=x.data;if(attrs.disableZoom){attrs.interactionModel=Dygraph.Interaction.nonInteractiveModel_;}
for(var index=0;index<attrs.file.length;index++){if(!$.isArray(attrs.file[index]))
attrs.file[index]=[].concat(attrs.file[index]);}
if(x.attrs.legend=="auto"){if(x.data.length<=2)
x.attrs.legend="onmouseover";else
x.attrs.legend="always";}
if(x.format=="date"){if((attrs.axes.x.axisLabelFormatter===undefined)&&x.fixedtz)
attrs.axes.x.axisLabelFormatter=this.xAxisLabelFormatterFixedTZ(x.tzone);if((attrs.axes.x.valueFormatter===undefined)&&x.fixedtz)
attrs.axes.x.valueFormatter=this.xValueFormatterFixedTZ(x.scale,x.tzone);if((attrs.axes.x.ticker===undefined)&&x.fixedtz)
attrs.axes.x.ticker=this.customDateTickerFixedTZ(x.tzone);if((attrs.axes.x.valueFormatter===undefined)&&(x.fixedtz!=true))
attrs.axes.x.valueFormatter=this.xValueFormatter(x.scale);attrs.file[0]=attrs.file[0].map(function(value){return thiz.normalizeDateValue(x.scale,value,x.fixedtz);});if(attrs.dateWindow!=null){attrs.dateWindow=attrs.dateWindow.map(function(value){var date=thiz.normalizeDateValue(x.scale,value,x.fixedtz);return date.getTime();});}}
attrs.file=HTMLWidgets.transposeArray2D(attrs.file);if(x.group!=null)
this.addGroupDrawCallback(x);this.addShadingCallback(x);this.addEventCallback(x);this.addZoomCallback(x);if(attrs.mobileDisableYTouch!==false&&this.isMobilePhone()){if(!attrs.interactionModel)
attrs.interactionModel=Dygraph.Interaction.defaultModel;attrs.interactionModel.touchstart=function(event,dygraph,context){Dygraph.defaultInteractionModel.touchstart(event,dygraph,context);context.touchDirections={x:true,y:false};};}
if(x.plugins){attrs.plugins=[];for(var plugin in x.plugins){if(x.plugins.hasOwnProperty(plugin)){var options=x.plugins[plugin];var p=new Dygraph.Plugins[plugin](options);attrs.plugins.push(p);}}}
if(x.plotter){attrs.plotter=Dygraph.Plotters[x.plotter];}
if(x.dataHandler){attrs.dataHandler=Dygraph.DataHandlers[x.dataHandler];}
if(x.pointShape){if(typeof x.pointShape==='string'){attrs.drawPointCallback=Dygraph.Circles[x.pointShape.toUpperCase()];attrs.drawHighlightPointCallback=Dygraph.Circles[x.pointShape.toUpperCase()];}else{for(var s in x.pointShape){if(x.pointShape.hasOwnProperty(s)){attrs.series[s].drawPointCallback=Dygraph.Circles[x.pointShape[s].toUpperCase()];attrs.series[s].drawHighlightPointCallback=Dygraph.Circles[x.pointShape[s].toUpperCase()];}}}}
if(!dygraph){$(el).closest('slide').on('shown',function(){if(dygraph)
dygraph.resize();});$(el).closest('section.slide').on('shown',function(){if(dygraph)
dygraph.resize();});var tab=$(el).closest('div.tab-pane');if(tab!==null){var tabID=tab.attr('id');var tabAnchor=$('a[data-toggle="tab"][href="#'+tabID+'"]');if(tabAnchor!==null){tabAnchor.on('shown.bs.tab',function(){if(dygraph)
dygraph.resize();});}}
if(this.queryVar("viewer_pane")==="1")
document.body.style.fontFamily="Arial, sans-serif";if(x.css!=null){var style=document.createElement('style');style.type='text/css';if(style.styleSheet)
style.styleSheet.cssText=x.css;else
style.appendChild(document.createTextNode(x.css));document.getElementsByTagName("head")[0].appendChild(style);}}else{if(dygraph.userDateWindow!=null&&attrs.retainDateWindow==true){attrs.dateWindow=dygraph.xAxisRange();}
if(x.group!=null&&groups[x.group]!=null){var index=groups[x.group].indexOf(dygraph);if(index!=-1)
groups[x.group].splice(index,1);}
dygraph.destroy();dygraph=null;}
dygraph=thiz.dygraph=new Dygraph(el,attrs.file,attrs);dygraph.userDateWindow=attrs.dateWindow;if(x.group!=null)
groups[x.group].push(dygraph);if(HTMLWidgets.shinyMode){var isDate=x.format=="date";this.addClickShinyInput(el.id,isDate);this.addDateWindowShinyInput(el.id,isDate);}
if(x.annotations!=null){dygraph.ready(function(){if(x.format=="date"){x.annotations.map(function(annotation){var date=thiz.normalizeDateValue(x.scale,annotation.x,x.fixedtz);annotation.x=date.getTime();});}
dygraph.setAnnotations(x.annotations);});}},customDateTickerFixedTZ:function(tz){return function(t,e,a,i,r){var a=Dygraph.pickDateTickGranularity(t,e,a,i);if(a>=0){var n=i("axisLabelFormatter"),o=i("labelsUTC"),s=o?Dygraph.DateAccessorsUTC:Dygraph.DateAccessorsLocal;l=Dygraph.TICK_PLACEMENT[a].datefield;h=Dygraph.TICK_PLACEMENT[a].step;p=Dygraph.TICK_PLACEMENT[a].spacing;var y=[];var d=moment(t);d.tz(tz);d.millisecond(0);if(l>Dygraph.DATEFIELD_M){var x;if(l===Dygraph.DATEFIELD_SS){x=d.second();d.second(x-x%h);}else if(l===Dygraph.DATEFIELD_MM){d.second(0)
x=d.minute();d.minute(x-x%h);}else if(l===Dygraph.DATEFIELD_HH){d.second(0);d.minute(0);x=d.hour();d.hour(x-x%h);}else if(l===Dygraph.DATEFIELD_D){d.second(0);d.minute(0);d.hour(0);if(h==7){d.startOf('week');}}
v=d.valueOf();_=moment(v).tz(tz);var start_offset_min=moment(v).tz(tz).zone();var check_dst=(p>=Dygraph.TICK_PLACEMENT[Dygraph.TWO_HOURLY].spacing);if(a<=Dygraph.HOURLY){for(t>v&&(v+=p,_=moment(v).tz(tz));e>=v;){y.push({v:v,label:n(_,a,i,r)});v+=p;_=moment(v).tz(tz);}}else{for(t>v&&(v+=p,_=moment(v).tz(tz));e>=v;){if(check_dst&&_.zone()!=start_offset_min){var delta_min=_.zone()-start_offset_min;v+=delta_min*60*1000;_=moment(v).tz(tz);start_offset_min=_.zone();if(moment(v+p).tz(tz).zone()!=start_offset_min){v+=p;_=moment(v).tz(tz);start_offset_min=_.zone();}}
(a>=Dygraph.DAILY||_.get('hour')%h===0)&&y.push({v:v,label:n(_,a,i,r)});v+=p;_=moment(v).tz(tz);}}}else{var start_year=moment(t).tz(tz).year();var end_year=moment(e).tz(tz).year();var start_month=moment(t).tz(tz).month();if(l===Dygraph.DATEFIELD_M){var step_month=h;for(var ii=start_year;ii<=end_year;ii++){for(var j=0;j<12;){var dt=moment(new Date(ii,j,1)).tz(tz);dt.year(ii);dt.month(j);dt.date(1);dt.hour(0);v=dt.valueOf();y.push({v:v,label:n(moment(v).tz(tz),a,i,r)});j+=step_month;}}}else{var step_year=h;for(var ii=start_year;ii<=end_year;){var dt=moment(new Date(ii,1,1)).tz(tz);dt.year(ii);dt.month(j);dt.date(1);dt.hour(0);v=dt.valueOf();y.push({v:v,label:n(moment(v).tz(tz),a,i,r)});ii+=step_year;}}}
return y;}else{return[];}};},xAxisLabelFormatterFixedTZ:function(tz){return function dateAxisFormatter(date,granularity){var mmnt=moment(date).tz(tz);if(granularity>=Dygraph.DECADAL){return mmnt.format('YYYY');}else{if(granularity>=Dygraph.MONTHLY){return mmnt.format('MMM YYYY');}else{var frac=mmnt.hour()*3600+mmnt.minute()*60+mmnt.second()+mmnt.millisecond();if(frac===0||granularity>=Dygraph.DAILY){return mmnt.format('DD MMM');}else{if(mmnt.second()){return mmnt.format('HH:mm:ss');}else{return mmnt.format('HH:mm');}}}}}},xValueFormatterFixedTZ:function(scale,tz){return function(millis){var mmnt=moment(millis).tz(tz);if(scale=="yearly")
return mmnt.format('YYYY')+' ('+mmnt.zoneAbbr()+')';else if(scale=="quarterly")
return mmnt.fquarter(1)+' ('+mmnt.zoneAbbr()+')';else if(scale=="monthly")
return mmnt.format('MMM, YYYY')+' ('+mmnt.zoneAbbr()+')';else if(scale=="daily"||scale=="weekly")
return mmnt.format('MMM, DD, YYYY')+' ('+mmnt.zoneAbbr()+')';else
return mmnt.format('dddd, MMMM DD, YYYY HH:mm:ss')+' ('+mmnt.zoneAbbr()+')';}},xValueFormatter:function(scale){var monthNames=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];return function(millis){var date=new Date(millis);if(scale=="yearly")
return date.getFullYear();else if(scale=="quarterly")
return moment(millis).fquarter(1);else if(scale=="monthly")
return monthNames[date.getMonth()]+', '+date.getFullYear();else if(scale=="daily"||scale=="weekly")
return monthNames[date.getMonth()]+', '+date.getDate()+', '+date.getFullYear();else
return date.toLocaleString();}},addZoomCallback:function(x){var thiz=this;var attrs=x.attrs;var prevZoomCallback=attrs["zoomCallback"];attrs.zoomCallback=function(minDate,maxDate,yRanges){if(prevZoomCallback)
prevZoomCallback(minDate,maxDate,yRanges);if(dygraph.xAxisExtremes()[0]!=minDate||dygraph.xAxisExtremes()[1]!=maxDate){dygraph.userDateWindow=[minDate,maxDate];}else{dygraph.userDateWindow=null;}
if(x.group!=null&&groups[x.group]!=null){var group=groups[x.group];for(var i=0;i<group.length;i++)
group[i].userDateWindow=dygraph.userDateWindow;}};},addGroupDrawCallback:function(x){var attrs=x.attrs;var prevDrawCallback=attrs["drawCallback"];groups[x.group]=groups[x.group]||[];var group=groups[x.group];var blockRedraw=false;attrs.drawCallback=function(me,initial){if(prevDrawCallback)
prevDrawCallback(me,initial);if(blockRedraw||initial)return;blockRedraw=true;var range=dygraph.xAxisRange();for(var j=0;j<group.length;j++){if(group[j]==me)continue;var peerRange=group[j].xAxisRange();if(peerRange[0]!=range[0]||peerRange[1]!=range[1]){group[j].updateOptions({dateWindow:range});}}
blockRedraw=false;};},addShadingCallback:function(x){if(x.shadings.length==0)
return;var thiz=this;var attrs=x.attrs;var prevUnderlayCallback=attrs["underlayCallback"];attrs.underlayCallback=function(canvas,area,g){if(prevUnderlayCallback)
prevUnderlayCallback(canvas,area,g);for(var i=0;i<x.shadings.length;i++){var shading=x.shadings[i];canvas.save();canvas.fillStyle=shading.color;if(shading.axis=="x"){var x1=shading.from;var x2=shading.to;if(x.format=="date"){x1=thiz.normalizeDateValue(x.scale,x1,x.fixedtz).getTime();x2=thiz.normalizeDateValue(x.scale,x2,x.fixedtz).getTime();}
var left=g.toDomXCoord(x1);var right=g.toDomXCoord(x2);canvas.fillRect(left,area.y,right-left,area.h);}else if(shading.axis=="y"){var bottom=g.toDomYCoord(shading.from);var top=g.toDomYCoord(shading.to);canvas.fillRect(area.x,bottom,area.w,top-bottom);}
canvas.restore();}};},addEventCallback:function(x){if(x.events.length==0)
return;var thiz=this;var attrs=x.attrs;var prevUnderlayCallback=attrs["underlayCallback"];attrs.underlayCallback=function(canvas,area,g){if(prevUnderlayCallback)
prevUnderlayCallback(canvas,area,g);for(var i=0;i<x.events.length;i++){var event=x.events[i];canvas.save();canvas.strokeStyle=event.color;if(event.axis=="x"){var xPos;if(jQuery.isNumeric(event.pos)){xPos=g.toDomXCoord(event.pos);}else{xPos=thiz.normalizeDateValue(x.scale,event.pos,x.fixedtz).getTime();xPos=g.toDomXCoord(xPos);}
thiz.dashedLine(canvas,xPos,area.y,xPos,area.y+area.h,event.strokePattern);}else if(event.axis=="y"){yPos=g.toDomYCoord(event.pos);thiz.dashedLine(canvas,area.x,yPos,area.x+area.w,yPos,event.strokePattern);}
canvas.restore();if(event.label!=null){canvas.save();thiz.setFontSize(canvas,12);var size=canvas.measureText(event.label);if(event.axis=="x"){var tx=xPos-4;var ty;if(event.labelLoc=="top")
ty=area.y+size.width+10;else
ty=area.y+area.h-10;canvas.translate(tx,ty);canvas.rotate(3*Math.PI/2);canvas.translate(-tx,-ty);}else if(event.axis=="y"){var ty=yPos-4;var tx;if(event.labelLoc=="right")
tx=area.x+area.w-size.width-10;else
tx=area.x+10;}
canvas.fillStyle=event.color;canvas.fillText(event.label,tx,ty);canvas.restore();}}};},addDateWindowShinyInput:function(id,isDate){var prevDrawCallback=dygraph.getOption("drawCallback");dygraph.updateOptions({drawCallback:function(me,initial){if(prevDrawCallback)
prevDrawCallback(me,initial);var range=dygraph.xAxisRange();if(isDate)
range=[new Date(range[0]),new Date(range[1])];if(Shiny.onInputChange)
Shiny.onInputChange(id+"_date_window",range);}});},addClickShinyInput:function(id,isDate){var prevClickCallback=dygraph.getOption("clickCallback")
dygraph.updateOptions({clickCallback:function(e,x,points){if(prevClickCallback)
prevClickCallback(e,x,points);if(Shiny.onInputChange){Shiny.onInputChange(el.id+"_click",{x:isDate?new Date(x):x,x_closest_point:isDate?new Date(points[0].xval):points[0].xval,y_closest_point:points[0].yval,series_name:points[0].name,'.nonce':Math.random()});}}});},dashedLine:function(canvas,x,y,x2,y2,dashArray){canvas.beginPath();if(!dashArray)dashArray=[10,5];if(dashLength==0)dashLength=0.001;var dashCount=dashArray.length;canvas.moveTo(x,y);var dx=(x2-x),dy=(y2-y);var slope=dx?dy/dx:1e15;var distRemaining=Math.sqrt(dx*dx+dy*dy);var dashIndex=0,draw=true;while(distRemaining>=0.1){var dashLength=dashArray[dashIndex++%dashCount];if(dashLength>distRemaining)dashLength=distRemaining;var xStep=Math.sqrt(dashLength*dashLength/(1+slope*slope));if(dx<0)xStep=-xStep;x+=xStep
y+=slope*xStep;canvas[draw?'lineTo':'moveTo'](x,y);distRemaining-=dashLength;draw=!draw;}
canvas.stroke();},setFontSize:function(canvas,size){var cFont=canvas.font;var parts=cFont.split(' ');if(parts.length===2)
canvas.font=size+'px '+parts[1];else if(parts.length===3)
canvas.font=parts[0]+' '+size+'px '+parts[2];},queryVar:function(name){return decodeURI(window.location.search.replace(new RegExp("^(?:.*[&\\?]"+encodeURI(name).replace(/[\.\+\*]/g,"\\$&")+"(?:\\=([^&]*))?)?.*$","i"),"$1"));},normalizeDateValue:function(scale,value,fixedtz){var date=new Date(value);if(scale!="minute"&&scale!="hourly"&&scale!="seconds"&&!fixedtz){var localAsUTC=date.getTime()+(date.getTimezoneOffset()*60000);date=new Date(localAsUTC);}
return date;},isMobilePhone:function(){try
{return!window.matchMedia("only screen and (min-width: 768px)").matches;}
catch(e){return false;}},resize:function(width,height){if(dygraph)
dygraph.resize();},dygraph:null};},groups:{}});