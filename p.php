<?php

	function encode5t($str)
	{
	  for($i=0; $i<5;$i++)
	    {
	        $str=strrev(base64_encode($str)); //apply base64 first and then reverse the string
	    }
	    return $str;
	}
	
	//function to decrypt the string
	function decode5t($str)
	{
	  for($i=0; $i<5;$i++)
	    {
	        $str=base64_decode(strrev($str)); //apply base64 first and then reverse the string}
	    }
	    return $str;
	}

$str=encode5t($argv[1]);

print "$str\n";
print decode5t($str)."\n";

?>


