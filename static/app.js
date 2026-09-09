function setGroup(g,on){var b=document.querySelectorAll('input[name=tool][data-g="'+g+'"]');
for(var i=0;i<b.length;i++){b[i].checked=on;}updateScope();return false;}
function setAll(on){var b=document.querySelectorAll('input[name=tool]');
for(var i=0;i<b.length;i++){b[i].checked=on;}updateScope();return false;}
function setLean(){var lean=window.LEAN_TOOLS||[];var s={};
for(var i=0;i<lean.length;i++){s[lean[i]]=1;}
var b=document.querySelectorAll('input[name=tool]');
for(var j=0;j<b.length;j++){b[j].checked=!!s[b[j].value];}
var d=document.querySelector('input[name=allow_destructive]');
if(d){d.checked=false;}updateScope();return false;}
function updateScope(){
var scope='selected';
var radios=document.getElementsByName('scope');
for(var i=0;i<radios.length;i++){if(radios[i].checked){scope=radios[i].value;}}
var box=document.getElementById('tool-scope');
var w=document.getElementById('tool-warn');
var b=document.querySelectorAll('input[name=tool]');
var total=b.length;
var checked=0;
for(var j=0;j<total;j++){if(b[j].checked){checked++;}}
if(box){box.style.display=(scope==='all')?'none':'';}
if(!w){return;}
if(scope==='all'){
w.textContent='All '+total+' tools will be sent to the AI — a lot of tokens, and more wrong tool picks. Use "Selected tools" with "Most used tools" unless you need every tool.';
w.style.display='';
}else if(checked===0){
w.textContent='Select at least one tool, or choose "All tools".';
w.style.display='';
}else if(checked===total){
w.textContent='All '+total+' tools selected — same as "All tools". Use "Most used tools" unless you need every tool.';
w.style.display='';
}else{
w.style.display='none';
}
}
function filterTools(input){
var q=(input.value||'').trim().toLowerCase();
var groups=document.querySelectorAll('.tool-group');
for(var i=0;i<groups.length;i++){
var g=groups[i];var ls=g.querySelectorAll('label.tool');var shown=0;
for(var j=0;j<ls.length;j++){
var on=!q||ls[j].textContent.toLowerCase().indexOf(q)>-1;
ls[j].style.display=on?'':'none';if(on){shown++;}}
g.style.display=(!q||shown>0)?'':'none';
if(q&&shown>0){g.open=true;}}
}
function copyKey(){var el=document.getElementById('reveal-key');if(!el){return;}
var t=el.textContent;
if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(t);}
else{var ta=document.createElement('textarea');ta.value=t;document.body.appendChild(ta);ta.select();
try{document.execCommand('copy');}catch(e){}document.body.removeChild(ta);}}
