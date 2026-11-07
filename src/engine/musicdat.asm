	arch 65816
;**********************************************************************
;*                                                                    *
;*                   P R O J E C T :   REALITY_ENGINE                 *
;*                                                                    *
;*                       SOUND/MUSIC DATA MODULE                      *
;*                                                                    *
;**********************************************************************

	incsrc "src/include/rage.inc"
	incsrc "src/include/rle.inc"
	incsrc "src/include/music.inc"


	if useSOUND != 0

;
;	* * * * * * *       MUSIC CHUNKS       * * * * * * *
;
;	(this port) tools/musicpage.py's pieces of at most 32 KB, one section each
;	(MUSIC_C0...), each inside one LoROM page: the CPU reads the chunks with
;	24-bit pointers, which must not cross a page.  The chunk and turbo tables
;	(musicdrv.asm) hold their LoROM addresses.
;
	!__p #= 0
	while !__p < 32
		%section(MUSIC_C!__p)
		if canreadfile1("data/RLDATA/MUSIC/MUSIC_C.P!__p", 0)
			incbin "data/RLDATA/MUSIC/MUSIC_C.P!__p"
		endif
		!__p #= !__p+1
	endwhile

	endif
