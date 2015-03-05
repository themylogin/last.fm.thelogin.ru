$(function(){
    var artistSliderTemplate = $(".artist-slider-template").html();
    var col1Template = $(".col-1-template").html();
    var col2Template = $(".col-2-template").html();
    var col3Template = $(".col-3-template").html();

    function connect()
    {
        var socket = new WebSocket("ws://192.168.0.1:8888/");
        socket.onmessage = function(msg){
            var response = $.parseJSON(msg.data);

            if (response.state == "play")
            {
                showMusic(response.currentartist, response.currentalbum, response.currentsong, response.currentpath);
            }
            else
            {
                showNoMusic();
            }
        }
        socket.onclose = function(){
            setTimeout(connect, 1000);
        };
    }
    connect();

    var currentArtist = null;
    var currentPath = null;
    function showMusic(artist, album, track, path)
    {
        if (artist != currentArtist)
        {
            currentArtist = artist;

            $.when(
                $.ajax("/dashboard/artist", {"data": {"artist": artist}})
            ).done(function(artist_data){
                var $oldCol1 = $(".col-1");
                var $oldCol2 = $(".col-2");
                var $newCol1 = $("<div/>").addClass("col-1").hide().html(col1Template).appendTo("body");
                var $newCol2 = $("<div/>").addClass("col-2").hide().html(col2Template).appendTo("body");
                var $artistSlider = $newCol1.find(".artist-slider");
                var $artistTitle = $newCol2.find(".artist-title");
                var $artistWiki = $newCol2.find(".artist-wiki");

                $artistSlider.html(artistSliderTemplate);
                $artistSlider.find(">div").attr("id", "artist-slider");
                var $slides = $artistSlider.find(".slides");
                $.each(artist_data.images, function(i, url){
                    $slides.append($("<div/>").append($("<img/>").attr("u", "image").attr("src", url.replace("http:/", "/static/artists/http")))
                                              .append($("<img/>").attr("u", "thumb").attr("src", url.replace("http:/", "/static/artists/min-size/77/http"))));
                });
                new $JssorSlider$("artist-slider", {
                    $AutoPlay: true,
                    $AutoPlayInterval: 5000,
                    $PauseOnHover: 0,

                    $DragOrientation: 3,
                    $ArrowKeyNavigation: true,
                    $SlideDuration: 800,

                    $SlideshowOptions: {
                        $Class: $JssorSlideshowRunner$,
                        $Transitions: [{$Duration:1200,x:1,$Easing:{$Left:$JssorEasing$.$EaseInOutQuart},$Opacity:2,$Brother:{$Duration:1200,x:-1,$Easing:{$Left:$JssorEasing$.$EaseInOutQuart},$Opacity:2}}],
                        $TransitionsOrder: 1,
                        $ShowLink: true
                    },

                    $ArrowNavigatorOptions: {
                        $Class: $JssorArrowNavigator$,
                        $ChanceToShow: 1
                    },

                    $ThumbnailNavigatorOptions: {
                        $Class: $JssorThumbnailNavigator$,
                        $ChanceToShow: 2,

                        $ActionMode: 1,
                        $SpacingX: 8,
                        $DisplayPieces: 10,
                        $ParkingPosition: 360
                    },

                    $FillMode: 5
                });

                $artistTitle.text(artist);
                $artistWiki.html(artist_data.wiki);
                setTimeout(function(){
                    if ($artistWiki.height() > 985)
                    {
                        var pixels = ($artistWiki.height() - 981);
                        var animate1, animate2;
                        animate1 = function(){
                            $artistWiki.animate({ top: -pixels }, pixels * 60, "linear", animate2);
                        };
                        animate2 = function(){
                            $artistWiki.animate({ top: 0 }, pixels / 4, "swing", animate1);
                        };
                        setTimeout(animate1, 5000);
                    }
                }, 0);

                $newCol1.fadeIn(500);
                $oldCol1.fadeOut(500, function(){
                    $oldCol1.remove();
                });
                $newCol2.fadeIn(500);
                $oldCol2.fadeOut(500, function(){
                    $oldCol2.remove();
                });
            });
        }

        if (path != currentPath)
        {
            currentPath = path;

            var $oldCol3 = $(".col-3");
            var $newCol3 = $("<div/>").addClass("col-3").hide().html(col3Template).appendTo("body");
            $newCol3.find(".album-cover").attr("src", "http://last.fm.thelogin.ru/static/covers/pad/%23191919/640/640/http/player.thelogin.ru/cover_for_file?path=" + encodeURIComponent(path));

            $newCol3.fadeIn(500);
            $oldCol3.fadeOut(500, function(){
                $oldCol3.remove();
            })
        }
    }
});
