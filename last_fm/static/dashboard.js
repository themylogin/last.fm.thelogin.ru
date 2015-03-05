$(function(){
    var artistSliderTemplate = $(".artist-slider-template").html();
    var col1Template = $(".col-1-template").html();
    var col2Template = $(".col-2-template").html();
    var col3Template = $(".col-3-template").html();

    var $container = $("#container");

    /*
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
    */

    // showMusic("Velvet Acid Christ", "", "Fun With Drugs", "Rave/Industrial/Velvet Acid Christ/1999 - Fun With Razors/Fun With Knives/05 - Fun With Drugs.flac");
    showMusic("Velvet Acid Christ", "", "Decypher", "Rave/Industrial/Velvet Acid Christ/1999 - Fun With Razors/Fun With Knives/01 - Decypher.flac");

    var currentArtist = null;
    var currentTrack = null;
    var currentPath = null;
    function showMusic(artist, album, track, path)
    {
        var artistChanged = artist != currentArtist;
        var trackChanged = track != currentTrack;
        var pathChanged = path != currentPath;
        currentArtist = artist;
        currentTrack = track;
        currentPath = path;

        var col2deferreds = [];

        if (artistChanged)
        {
            var artistWikiDeferred = $.Deferred();
            col2deferreds.push(artistWikiDeferred);

            $.ajax("/dashboard/artist", {"data": {"artist": artist}}).done(function(artist_data){
                var $oldCol1 = $(".col-1");
                var $newCol1 = $("<div/>").addClass("col-1").hide().html(col1Template).appendTo($container);
                var $artistSlider = $newCol1.find(".artist-slider");

                shuffle(artist_data.images);
                setupArtistSlider($artistSlider, artist_data.images);

                $newCol1.fadeIn(500);
                $oldCol1.fadeOut(500, function(){
                    $oldCol1.remove();
                });

                artistWikiDeferred.resolve({"wiki": artist_data.wiki});
            });
        }

        if (artistChanged || trackChanged)
        {
            var lyricsDeferred = $.Deferred();
            col2deferreds.push(lyricsDeferred);

            $.ajax("http://player.thelogin.ru/lyrics", {"data": {"artist": artist, "title": track}}).done(function(lyrics){
                lyricsDeferred.resolve({"lyrics": lyrics.replace(/\n/g, "<br />")});
            });
        }

        if (pathChanged)
        {
            currentPath = path;

            var $oldCol3 = $(".col-3");
            var $newCol3 = $("<div/>").addClass("col-3").hide().html(col3Template).appendTo($container);
            $newCol3.find(".album-cover").attr("src", "http://last.fm.thelogin.ru/static/covers/pad/%23191919/640/640/http/player.thelogin.ru/cover_for_file?path=" + encodeURIComponent(path));

            $newCol3.fadeIn(500);
            $oldCol3.fadeOut(500, function(){
                $oldCol3.remove();
            })
        }

        if (col2deferreds.length)
        {
            $.when.apply($, col2deferreds).then(function(){
                var data = {};
                $.each(arguments, function(i, arg){
                    $.each(arg, function(k, v){
                        data[k] = v;
                    });
                });

                function calculateHeights(container_class, callback){
                    var $container = $("<div/>").addClass(container_class).css("visibility", "hidden").appendTo("body");

                    var $cols = {};
                    $.each(data, function(k, v){
                        $cols[k] = $("<div/>").addClass("col-2").css("visibility", "hidden").html("<div>" + v + "</div>").appendTo($container);
                    });
                    setTimeout(function(){
                        var heights = {};
                        $.each($cols, function(k, v){
                            heights[k] = v.find(">div").height();
                        });

                        $container.remove();

                        callback(heights);
                    }, 0);
                }

                var totalHeight = 1060;
                var headerHeight = 69;
                var minWikiHeight = 240;
                function calculateProportionalHeights(heights)
                {
                    var wikiHeight = minWikiHeight;
                    var lyricsHeight = totalHeight - 2 * headerHeight - wikiHeight;
                    if (heights["lyrics"] < lyricsHeight)
                    {
                        wikiHeight += lyricsHeight - heights["lyrics"];
                        lyricsHeight = heights["lyrics"];                        
                    }
                    if (heights["wiki"] < wikiHeight)
                    {
                        wikiHeight = heights["wiki"];
                    }
                    return {
                        "wiki": wikiHeight,
                        "lyrics": lyricsHeight
                    };
                }

                calculateHeights("", function(heights){
                    if (heights["lyrics"] < totalHeight - minWikiHeight)
                    {
                        setup$col2(artist, track, data, calculateProportionalHeights(heights));
                    }
                    else
                    {
                        calculateHeights("col-2-2", function(heights){
                            $container.addClass("col-2-2");

                            var col2heights = calculateProportionalHeights({
                                "wiki": heights["wiki"],
                                "lyrics": heights["lyrics"] - totalHeight
                            });

                            setup$col2(artist, track, data, col2heights);

                            var $col2_2 = $("<div/>").addClass("col-2-2").html(col2Template).appendTo($container);

                            $col2_2.find(".artist-title").remove();
                            $col2_2.find(".artist-wiki").remove();

                            $col2_2.find(".track-title").remove();
                            $col2_2.find(".track-lyrics-wrap").css("height", totalHeight);
                            $col2_2.find(".track-lyrics").css("top", -col2heights["lyrics"]).html(data["lyrics"]);

                            var $artistSlider = $(".col-1 .artist-slider");
                            var index = $artistSlider.data("$JssorSlider$").$CurrentIndex();
                            setupArtistSlider($artistSlider, $artistSlider.data("images"), index);
                        });
                    }

                    /*
                    var wikiHeight, lyricsHeight;
                    wikiHeight = 120;
                    lyricsHeight = totalHeight - wikiHeight;
                    if (heights["lyrics"] < lyricsHeight)
                    {
                        wikiHeight += lyricsHeight - heights["lyrics"];
                        lyricsHeight = heights["lyrics"];                        
                    }
                    if (heights["wiki"] < wikiHeight)
                    {
                        wikiHeight = heights["wiki"];
                    }

                    var $col2 = $("<div/>").addClass("col-2").html(col2Template).appendTo("body");

                    $col2.find(".artist-title").text(artist);
                    $col2.find(".artist-wiki-wrap").css("height", wikiHeight);
                    $col2.find(".artist-wiki").html(data["wiki"]);

                    $col2.find(".track-title").text(track);
                    $col2.find(".track-lyrics-wrap").css("height", lyricsHeight);
                    $col2.find(".track-lyrics").html(data["lyrics"]);
                    */
                });
            });
        }
    }

    function setupArtistSlider($artistSlider, images, startIndex)
    {
        if (startIndex === undefined)
        {
            startIndex = 0;
        }

        $artistSlider.html(artistSliderTemplate);

        var $slides = $artistSlider.find(".slides");
        $.each(images, function(i, url){
            $slides.append($("<div/>").append($("<img/>").attr("u", "image").attr("src", url.replace("http:/", "/static/artists/http")))
                                      .append($("<img/>").attr("u", "thumb").attr("src", url.replace("http:/", "/static/artists/min-size/77/http"))));
        });

        $artistSlider.find(">div").attr("id", "artist-slider");
        $artistSlider.data("images", images).data("$JssorSlider$", new $JssorSlider$("artist-slider", {
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

            $FillMode: 5,

            $StartIndex: startIndex,
        }));
    }

    function setup$col2(artist, track, data, heights)
    {
        var $col2 = $("<div/>").addClass("col-2").html(col2Template).appendTo($container);

        $col2.find(".artist-title").text(artist);
        $col2.find(".artist-wiki-wrap").css("height", heights["wiki"]);
        $col2.find(".artist-wiki").html(data["wiki"]);
        scrollArtistWiki(heights["wiki"], $col2.find(".artist-wiki"));

        $col2.find(".track-title").text(track);
        $col2.find(".track-lyrics-wrap").css("height", heights["lyrics"]);
        $col2.find(".track-lyrics").html(data["lyrics"]);

        return $col2;
    }

    function scrollArtistWiki(height, $artistWiki)
    {
        setTimeout(function(){
            if ($artistWiki.height() > height)
            {
                var pixels = $artistWiki.height() - height;
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
    }

    function shuffle(array) {
      var currentIndex = array.length, temporaryValue, randomIndex ;

      // While there remain elements to shuffle...
      while (0 !== currentIndex) {

        // Pick a remaining element...
        randomIndex = Math.floor(Math.random() * currentIndex);
        currentIndex -= 1;

        // And swap it with the current element.
        temporaryValue = array[currentIndex];
        array[currentIndex] = array[randomIndex];
        array[randomIndex] = temporaryValue;
      }

      return array;
    }
});
